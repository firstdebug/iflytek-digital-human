#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Asynchronously upload pending JSON telemetry snapshots."""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from telemetry_common import (STATE_LOCK_PATH, TELEMETRY_DIR, consent_metadata,
                              file_lock, is_enabled, load_state, now_iso,
                              save_state, sanitize_completion_detail)

CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config' / 'telemetry.json'
UPLOADER_LOCK_PATH = TELEMETRY_DIR / 'uploader.lock'

DEFAULT_CONFIG = {
    'endpoint': 'http://localhost:13042/zs_admin/avatarTelemetry/report',
    'timeout_ms': 3000,
    'batch_size': 50,
    'retry_backoff_minutes': [1, 5, 30, 120],
    'schema_version': '1.4',
}

PERMANENT_REJECTION_REASONS = {
    'anonymousId_required', 'anonymousId_mismatch', 'revision_invalid',
    'startedAt_invalid', 'status_invalid',
    'workflowId_and_skillName_required', 'source_invalid', 'firstAt_invalid',
    'invalid_record', 'batch_too_large',
}


def load_config(override_endpoint=None):
    config = dict(DEFAULT_CONFIG)
    try:
        if CONFIG_PATH.exists():
            config.update(json.loads(CONFIG_PATH.read_text(encoding='utf-8')))
    except Exception:
        pass
    if override_endpoint:
        config['endpoint'] = override_endpoint
    return config


def load_upload_state():
    with file_lock(STATE_LOCK_PATH, timeout=2.0) as acquired:
        if not acquired:
            return {'retry_count': 0, 'last_attempt': None}
        value = load_state().get('upload') or {}
        return dict(value) if isinstance(value, dict) else {
            'retry_count': 0, 'last_attempt': None}


def save_upload_state(value):
    with file_lock(STATE_LOCK_PATH, timeout=2.0) as acquired:
        if not acquired:
            return False
        state = load_state()
        upload = state.setdefault('upload', {})
        upload['retry_count'] = int(value.get('retry_count', 0) or 0)
        upload['last_attempt'] = value.get('last_attempt')
        upload.setdefault('last_ack_at', None)
        save_state(state)
        return True


# Backward-compatible names for callers and tests.
load_state_file = load_upload_state
save_state_file = save_upload_state


def should_attempt(config, state):
    last = state.get('last_attempt')
    if not last:
        return True, None
    try:
        parsed = datetime.fromisoformat(str(last).replace('Z', '+00:00'))
    except Exception:
        return True, None
    retries = int(state.get('retry_count', 0) or 0)
    backoff = config.get('retry_backoff_minutes') or [1]
    wait_min = backoff[min(max(retries - 1, 0), len(backoff) - 1)] if retries else 0
    remaining = wait_min - (datetime.now(timezone.utc) - parsed).total_seconds() / 60
    if remaining > 0:
        return False, '退避中：还需等待 {:.1f} 分钟'.format(remaining)
    return True, None


def _safe_detail(raw):
    if not raw:
        return None
    if isinstance(raw, dict):
        clean = sanitize_completion_detail(raw)
        return json.dumps(clean, ensure_ascii=False, separators=(',', ':'))
    try:
        clean = sanitize_completion_detail(json.loads(raw))
        return json.dumps(clean, ensure_ascii=False, separators=(',', ':'))
    except (TypeError, ValueError):
        return None


def collect(state, limit):
    workflows = []
    for item in sorted(state.get('workflows', []),
                       key=lambda x: x.get('started_at') or ''):
        if item.get('upload_status') != 'pending':
            continue
        workflows.append({
            'workflowId': item['workflow_id'],
            'workflowType': item.get('workflow_type'),
            'anonymousId': item.get('anonymous_id'),
            'startedAt': item.get('started_at'),
            'endedAt': item.get('ended_at'),
            'status': item.get('status'),
            'hasAvatarSignal': item.get('has_avatar_signal', 0),
            'completionMethod': item.get('completion_method'),
            'completionDetail': _safe_detail(item.get('completion_detail')),
            'os': item.get('os'),
            'pluginVersion': item.get('plugin_version'),
            'revision': int(item.get('revision') or 1),
            '_revision': int(item.get('revision') or 1),
        })
        if len(workflows) >= limit:
            break

    invocations = []
    for item in sorted(state.get('invocations', []),
                       key=lambda x: x.get('first_at') or ''):
        if item.get('upload_status') != 'pending':
            continue
        invocations.append({
            'invocationId': item['invocation_id'],
            'workflowId': item.get('workflow_id'),
            'skillName': item.get('skill_name'),
            'anonymousId': item.get('anonymous_id'),
            'source': item.get('source'),
            'firstAt': item.get('first_at'),
            'lastAt': item.get('last_at') or item.get('first_at'),
            'revision': int(item.get('revision') or 1),
            '_revision': int(item.get('revision') or 1),
        })
        if len(invocations) >= limit:
            break
    return workflows, invocations


def post(config, payload):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        config['endpoint'], data=body, method='POST',
        headers={'Content-Type': 'application/json; charset=utf-8'})
    with urllib.request.urlopen(request,
                                timeout=config.get('timeout_ms', 3000) / 1000.0) as response:
        return json.loads(response.read().decode('utf-8'))


def _payload(config, workflows, invocations, consent):
    anonymous_id = (workflows[0].get('anonymousId') if workflows else
                    invocations[0].get('anonymousId'))
    return {
        'schemaVersion': config.get('schema_version', DEFAULT_CONFIG['schema_version']),
        'privacyNoticeVersion': consent['privacyNoticeVersion'],
        'consentedAt': consent['consentedAt'],
        'anonymousId': anonymous_id,
        'workflows': [{k: v for k, v in item.items() if not k.startswith('_')}
                      for item in workflows],
        'invocations': [{k: v for k, v in item.items() if not k.startswith('_')}
                        for item in invocations],
    }


def _mark_item(state, collection, key, value, revision, status):
    for item in state.get(collection, []):
        if item.get(key) == value and int(item.get('revision') or 1) == revision:
            item['upload_status'] = status
            item['updated_at'] = now_iso()
            return True
    return False


def apply_response(sent_state, workflows, invocations, data):
    """Apply ACKs only when the current revision equals the sent revision."""
    changed = False
    workflow_revisions = {item['workflowId']: item['_revision'] for item in workflows}
    invocation_revisions = {item['invocationId']: item['_revision'] for item in invocations}
    accepted_wf = set(data.get('acceptedWorkflowIds') or [])
    accepted_inv = set(data.get('acceptedInvocationIds') or [])
    for identifier in accepted_wf:
        if identifier in workflow_revisions:
            changed = _mark_item(sent_state, 'workflows', 'workflow_id', identifier,
                                 workflow_revisions[identifier], 'uploaded') or changed
    for identifier in accepted_inv:
        if identifier in invocation_revisions:
            changed = _mark_item(sent_state, 'invocations', 'invocation_id', identifier,
                                 invocation_revisions[identifier], 'uploaded') or changed
    for rejected in data.get('rejected') or []:
        identifier = rejected.get('id')
        reason = rejected.get('reason')
        if reason not in PERMANENT_REJECTION_REASONS:
            continue
        if identifier in workflow_revisions:
            changed = _mark_item(sent_state, 'workflows', 'workflow_id', identifier,
                                 workflow_revisions[identifier], 'dead_letter') or changed
        if identifier in invocation_revisions:
            changed = _mark_item(sent_state, 'invocations', 'invocation_id', identifier,
                                 invocation_revisions[identifier], 'dead_letter') or changed
    if changed:
        sent_state.setdefault('upload', {})['last_ack_at'] = now_iso()
    return changed


def pending_snapshot(limit):
    with file_lock(STATE_LOCK_PATH, timeout=2.0) as acquired:
        if not acquired:
            return None, None
        return collect(load_state(), limit)


def acknowledge(workflows, invocations, data):
    with file_lock(STATE_LOCK_PATH, timeout=2.0) as acquired:
        if not acquired:
            return None
        current = load_state()
        changed = apply_response(current, workflows, invocations, data)
        if changed:
            save_state(current)
        return changed


def upload_all(config, upload_state, post_fn=post):
    total_wf = total_inv = 0
    while True:
        consent = consent_metadata(config.get('endpoint'))
        if consent is None:
            break
        workflows, invocations = pending_snapshot(
            int(config.get('batch_size', 50)))
        if workflows is None:
            break
        if not workflows and not invocations:
            break
        data = post_fn(config, _payload(config, workflows, invocations, consent)).get('data') or {}
        acknowledged = acknowledge(workflows, invocations, data)
        if acknowledged is None:
            upload_state['retry_count'] = int(upload_state.get('retry_count', 0)) + 1
            upload_state['last_attempt'] = now_iso()
            save_upload_state(upload_state)
            break
        accepted_wf = {x for x in data.get('acceptedWorkflowIds') or []
                       if x in {w['workflowId'] for w in workflows}}
        accepted_inv = {x for x in data.get('acceptedInvocationIds') or []
                        if x in {i['invocationId'] for i in invocations}}
        total_wf += len(accepted_wf)
        total_inv += len(accepted_inv)
        retryable = [item for item in data.get('rejected') or []
                     if item.get('reason') not in PERMANENT_REJECTION_REASONS]
        upload_state['retry_count'] = (int(upload_state.get('retry_count', 0)) + 1
                                       if retryable else 0)
        upload_state['last_attempt'] = now_iso()
        save_upload_state(upload_state)
        if data.get('rejected') or not accepted_wf and not accepted_inv:
            break
    return total_wf, total_inv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', default=None)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if not is_enabled():
        print('telemetry disabled - nothing to upload')
        return
    config = load_config(args.endpoint)
    if not is_enabled(config.get('endpoint')):
        print('telemetry disabled for this endpoint - nothing to upload')
        return
    upload_state = load_upload_state()
    if not args.force and not args.dry_run:
        allowed, reason = should_attempt(config, upload_state)
        if not allowed:
            print(reason)
            return
    with file_lock(UPLOADER_LOCK_PATH, timeout=0.1) as acquired:
        if not acquired:
            print('uploader already running')
            return
        workflows, invocations = pending_snapshot(int(config.get('batch_size', 50)))
        if workflows is None:
            print('state busy - retry later')
            return
        if not workflows and not invocations:
            print('nothing to upload')
            return
        consent = consent_metadata(config.get('endpoint'))
        if consent is None:
            return
        if args.dry_run:
            print('POST {}'.format(config['endpoint']))
            print(json.dumps(_payload(config, workflows, invocations, consent),
                             ensure_ascii=False, indent=2))
            return
        try:
            wf_count, inv_count = upload_all(config, upload_state)
            print('uploaded: {} workflow(s), {} invocation(s)'.format(wf_count, inv_count))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            upload_state['retry_count'] = int(upload_state.get('retry_count', 0)) + 1
            upload_state['last_attempt'] = now_iso()
            save_upload_state(upload_state)
            print('upload failed ({}), retry #{} scheduled'.format(type(exc).__name__, upload_state['retry_count']))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('uploader error: {}'.format(exc))
    sys.exit(0)
