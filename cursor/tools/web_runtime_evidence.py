#!/usr/bin/env python3
"""Collect browser runtime evidence for Web SDK delivery.

This tool opens the prepared local Web SDK page, clicks the start button,
performs the requested interaction, and writes `.runtime/web-runtime-evidence.json`.
It is the deterministic evidence producer for `web_delivery.py`; agents should
not hand-write the evidence file.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


EVIDENCE_NAME = "web-runtime-evidence.json"
STATE_NAME = "web-delivery.json"


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, str(path))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _runtime_dir(project):
    return project / ".runtime"


def _state(project):
    return _read_json(_runtime_dir(project) / STATE_NAME) or {}


def _runner_source():
    return r"""
import { chromium } from 'playwright';

const options = JSON.parse(process.argv[2]);
const errors = [];
const warnings = [];
const responses = [];

async function launchBrowser() {
  const attempts = [
    { channel: 'chrome', headless: true },
    { channel: 'msedge', headless: true },
    { headless: true }
  ];
  const failures = [];
  for (const attempt of attempts) {
    try {
      const browser = await chromium.launch(attempt);
      return { browser, launch: attempt.channel || 'chromium' };
    } catch (error) {
      failures.push(`${attempt.channel || 'chromium'}:${error.message.split('\n')[0]}`);
    }
  }
  throw new Error(`browser_launch_failed:${failures.join('|')}`);
}

async function waitFor(page, check, timeoutMs, label) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    if (await page.evaluate(check)) return true;
    await page.waitForTimeout(500);
  }
  errors.push(`timeout:${label}`);
  return false;
}

async function clickFirst(page, selectors, label) {
  for (const selector of selectors) {
    const locator = selector.role
      ? page.getByRole(selector.role, { name: selector.name })
      : page.locator(selector.css);
    try {
      if (await locator.first().isVisible({ timeout: 1000 })) {
        await locator.first().click({ timeout: 30000 });
        return true;
      }
    } catch (_error) {
    }
  }
  errors.push(`missing_click_target:${label}`);
  return false;
}

async function fillFirst(page, selectors, value, label) {
  for (const selector of selectors) {
    const locator = selector.role
      ? page.getByRole(selector.role, { name: selector.name })
      : page.locator(selector.css);
    try {
      if (await locator.first().isVisible({ timeout: 1000 })) {
        await locator.first().fill(value, { timeout: 30000 });
        return true;
      }
    } catch (_error) {
    }
  }
  errors.push(`missing_fill_target:${label}`);
  return false;
}

const launched = await launchBrowser();
const browser = launched.browser;
const page = await browser.newPage({
  viewport: { width: options.viewportWidth, height: options.viewportHeight }
});

page.on('pageerror', error => errors.push(`pageerror:${error.message}`));
page.on('console', message => {
  const text = message.text();
  if (message.type() === 'error') errors.push(`console:${text}`);
  if (message.type() === 'warning' || message.type() === 'warn') {
    warnings.push(text);
  }
});
page.on('response', response => {
  const url = response.url();
  if (url.includes('/api/config') || url.includes('/api/avatar-auth')) {
    responses.push({ url, status: response.status() });
  }
});

try {
  await page.goto(options.url, { waitUntil: 'domcontentloaded', timeout: options.timeoutMs });

  await clickFirst(page, [
    { css: '#start-button' },
    { role: 'button', name: /启动|开始|Start/i }
  ], 'start');

  const connected = await waitFor(
    page,
    () => {
      const bodyHas = text => document.body && document.body.innerText.includes(text);
      return bodyHas('已连接') || Boolean(window.__avatarEvidence?.connected);
    },
    options.timeoutMs,
    'connected'
  );
  const streamStart = await waitFor(
    page,
    () => {
      const bodyHas = text => document.body && document.body.innerText.includes(text);
      return bodyHas('云端推流已开始') || Boolean(window.__avatarEvidence?.stream_start);
    },
    options.timeoutMs,
    'stream_start'
  );
  const firstFrame = await waitFor(
    page,
    () => {
      const video = document.querySelector('#avatar-wrapper video, video');
      return Boolean(video && video.readyState >= 1);
    },
    options.timeoutMs,
    'first_frame'
  );

  let interactionPassed = false;
  if (options.interaction === 'text') {
    await fillFirst(page, [
      { css: '#message' },
      { role: 'textbox', name: /输入文本|文本|message/i }
    ], options.text, 'message');
    await clickFirst(page, [
      { css: '#send-button' },
      { role: 'button', name: /发送|Send/i }
    ], 'send');
    interactionPassed = await waitFor(
    page,
    () => {
      const bodyHas = text => document.body && document.body.innerText.includes(text);
      return bodyHas('文本已发送') || Boolean(window.__avatarEvidence?.target_interaction_passed);
    },
    options.timeoutMs,
    'text'
  );
  } else {
    errors.push(`unsupported_interaction:${options.interaction}`);
  }

  const dom = await page.evaluate((interaction) => {
    const statusText = document.querySelector('#status')?.textContent || '';
    const bodyText = document.body?.innerText || '';
    const video = document.querySelector('#avatar-wrapper video, video');
    const audio = document.querySelector('#avatar-wrapper audio, audio');
    const pageEvidence = window.__avatarEvidence || {};
    return {
      status_text: statusText,
      body_text_sample: bodyText.slice(0, 500),
      video_element_found: Boolean(video),
      video_ready_state: video ? video.readyState : null,
      video_current_time: video ? video.currentTime : null,
      audio_element_found: Boolean(audio),
      window_evidence: pageEvidence,
      target_interaction: interaction
    };
  }, options.interaction);

  const evidence = {
    source: 'playwright',
    url: options.url,
    browser: launched.launch,
    collected_at: new Date().toISOString(),
    prepared_at_epoch: options.preparedAtEpoch,
    credential_fingerprint: options.credentialFingerprint,
    connected,
    stream_start: streamStart,
    first_frame: firstFrame && dom.video_element_found,
    target_interaction: options.interaction,
    target_interaction_passed: interactionPassed,
    errors,
    warnings,
    responses,
    checks: dom
  };
  console.log(JSON.stringify(evidence, null, 2));
} finally {
  await browser.close();
}
"""


def _run_node(project, options):
    runtime = _runtime_dir(project)
    runner = runtime / "web-runtime-evidence-runner.mjs"
    runner.write_text(textwrap.dedent(_runner_source()).strip() + "\n", encoding="utf-8")
    command = ["node", str(runner), json.dumps(options, ensure_ascii=False)]
    return subprocess.run(
        command,
        cwd=str(project),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=max(30, int(options["timeoutMs"] / 1000) * 4),
    )


def collect(project, url=None, interaction="text", text=None, timeout_ms=120000):
    project = Path(project).resolve()
    runtime = _runtime_dir(project)
    state = _state(project)
    selected_url = url or state.get("url")
    if not selected_url:
        return {
            "status": "failed",
            "issues": ["url_missing"],
        }, 2

    options = {
        "url": selected_url,
        "interaction": interaction,
        "text": text or "你好，请用一句话介绍你自己。",
        "timeoutMs": int(timeout_ms),
        "viewportWidth": 1440,
        "viewportHeight": 1200,
        "preparedAtEpoch": state.get("prepared_at_epoch"),
        "credentialFingerprint": state.get("credential_fingerprint"),
    }
    try:
        result = _run_node(project, options)
    except subprocess.TimeoutExpired:
        return {"status": "failed", "issues": ["runtime_evidence_timeout"]}, 2
    except OSError as exc:
        return {"status": "failed", "issues": ["node_unavailable:" + exc.__class__.__name__]}, 2

    if result.returncode != 0:
        issue = "runtime_evidence_runner_failed"
        if "Cannot find package 'playwright'" in result.stderr or "ERR_MODULE_NOT_FOUND" in result.stderr:
            issue = "playwright_dependency_missing"
        if "Executable doesn't exist" in result.stderr:
            issue = "playwright_browser_missing"
        return {
            "status": "failed",
            "issues": [issue],
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "next_action": {
                "commands": [
                    "npm install --save-dev playwright",
                    "npx playwright install chromium",
                ]
            },
        }, 2

    try:
        evidence = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "status": "failed",
            "issues": ["runtime_evidence_json_parse_failed"],
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }, 2

    evidence_path = runtime / EVIDENCE_NAME
    _write_json_atomic(evidence_path, evidence)
    issues = []
    for name in ("connected", "stream_start", "first_frame"):
        if evidence.get(name) is not True:
            issues.append(name)
    if evidence.get("target_interaction_passed") is not True:
        issues.append(interaction)
    if evidence.get("errors"):
        issues.append("runtime_errors")
    status = "success" if not issues else "failed"
    return {
        "status": status,
        "evidence": str(evidence_path),
        "issues": issues,
        "url": selected_url,
    }, 0 if not issues else 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--url")
    parser.add_argument("--interaction", choices=("text", "voice", "audio"), default="text")
    parser.add_argument("--text", default=None)
    parser.add_argument("--timeout-ms", type=int, default=120000)
    args = parser.parse_args(argv)
    payload, code = collect(
        args.project,
        url=args.url,
        interaction=args.interaction,
        text=args.text,
        timeout_ms=args.timeout_ms,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
