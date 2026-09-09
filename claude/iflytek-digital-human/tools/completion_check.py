#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完成判据：读取交付时落盘的标记文件，不扫盘。

在 SessionEnd 由 tracker 调用，也可手动跑：
  python tools/completion_check.py --cwd . --since 2026-08-04T00:00:00Z

返回 (method, detail)：
  method  verification_flag | artifacts_file | artifact | none
  detail  命中的证据（路径、命中的键），JSON 可序列化的 dict

**只读固定路径，不做任何目录遍历。** 原先会走 os.walk 去找 APK 和 dist
产物，在 home 目录这类大树上要几秒，把 UserPromptSubmit 钩子（超时几秒）
直接拖死，连本轮的 slash 调用一起丢掉。

判定改由模型负责：skill 在交付时把结果写进这三个固定位置之一，这里只确认
文件存在且内容有效。模型看得到整段对话，比扫盘更清楚有没有真的交付成功。
  .runtime/verification-result.json  avatar-verification 的验证结论（最强）
  .runtime/artifacts.json            平台侧交付物 ID（模板/直播间/知识库）
  .env                               凭据配置类工作流的产物
"""

import json
import sys
from pathlib import Path


def _iso_to_epoch(iso):
    """ISO8601 UTC 串 → epoch 秒。

    库里存的是带 Z 的 UTC。必须显式标记 tzinfo=utc —— 曾经用
    strptime().timestamp()，那是按本地时区解释的，在 UTC+8 下算出来的
    时间点早 8 小时，导致陈旧检查放过 8 小时内的任何旧文件。
    """
    if not iso:
        return 0
    try:
        from datetime import datetime, timezone
        s = iso.rstrip('Z').split('.')[0]
        return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S').replace(
            tzinfo=timezone.utc).timestamp()
    except Exception:
        return 0


# ------------------------------------------------------- 各类型验证
# 全部是固定路径的单文件读取，O(1)，没有任何目录遍历。

def _is_fresh(path, since_epoch):
    """Return whether a marker belongs to the current workflow."""
    if not since_epoch:
        return True
    try:
        return path.stat().st_mtime >= since_epoch
    except OSError:
        return False


def check_verification_flag(root, since_epoch=0):
    """avatar-verification 落盘的验证结果 —— 最强证据。

    这份文件由模型在跑完验证后写入，它看得到整段对话，
    比在磁盘上猜产物可靠。
    """
    for cand in (Path(root) / '.runtime' / 'verification-result.json',
                 Path(root) / 'verification-result.json'):
        if not cand.is_file() or not _is_fresh(cand, since_epoch):
            continue
        try:
            data = json.loads(cand.read_text(encoding='utf-8'))
        except Exception:
            continue
        if data.get('ready_to_deliver') is True:
            return ('verification_flag',
                    {'source': str(cand),
                     'issues_found': data.get('issues_found'),
                     'issues_fixed': data.get('issues_fixed')})
        # A failed/pending gate is normally recoverable within the same
        # business workflow. Only an explicit terminal marker may close it;
        # ordinary `ready_to_deliver: false` remains in progress.
        if (data.get('ready_to_deliver') is False
                and data.get('terminal_failure') is True):
            return ('verification_flag',
                    {'source': str(cand), 'failed': True,
                     'remaining': data.get('remaining_issues')})
    return None




def check_artifacts_json(root, since_epoch=0):
    """平台侧交付物（模板链接/直播间/知识库 ID）—— 本地无产物，只能记 ID。"""
    for cand in (Path(root) / '.runtime' / 'artifacts.json',
                 Path(root) / 'artifacts.json'):
        if not cand.is_file() or not _is_fresh(cand, since_epoch):
            continue
        try:
            data = json.loads(cand.read_text(encoding='utf-8'))
        except Exception:
            continue
        keys = [k for k in ('template_url', 'live_url', 'scene_id',
                            'lib_id', 'anchor_id') if data.get(k)]
        if keys:
            return ('artifacts_file', {'source': str(cand), 'found': keys})
    return None


CRED_KEYS = ('XF_APP_ID', 'XF_API_SECRET', 'XF_API_KEY', 'APP_ID', 'APPID')


def check_env_credentials(root, since_epoch):
    """凭据配置类工作流的产物就是一份填好的 .env。

    只检查键名存在且值非空，**不读取也不记录任何值**。
    """
    for name in ('.env', '.env.local'):
        p = Path(root) / name
        if not p.is_file():
            continue
        try:
            if since_epoch and p.stat().st_mtime < since_epoch:
                continue
            filled = 0
            for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, _, v = line.partition('=')
                k = k.strip().upper()
                if any(c in k for c in CRED_KEYS) and v.strip():
                    filled += 1
            if filled >= 2:  # 至少 appId + 一个密钥
                return ('artifact', {'env_file': name, 'filled_keys': filled})
        except OSError:
            continue
    return None


# ------------------------------------------------------- 入口

# 判定为"完成"的 method
COMPLETION_METHODS = ('verification_flag', 'artifact', 'artifacts_file')


def detect(cwd='.', since_iso=None, workflow_type=None):
    """按优先级返回 (method, detail)，找不到返回 ('none', {})。

    三次固定路径的文件读取，与工程大小无关。workflow_type 保留在签名里
    只为兼容既有调用方 —— 判据对所有类型都一样，因为标记文件是由对应
    skill 自己写的，写了就说明那条路径确实交付到位了。
    """
    root = Path(cwd).resolve()
    since = _iso_to_epoch(since_iso)

    checks = [lambda: check_verification_flag(root, since)]
    # A local SDK project is not deliverable merely because a scene/resource
    # id was created. It needs the runtime verification marker produced after
    # connection, stream and first-frame checks.
    if workflow_type != 'sdk_integration':
        checks.extend((lambda: check_artifacts_json(root, since),
                       lambda: check_env_credentials(root, since)))

    for fn in checks:
        try:
            r = fn()
        except Exception:
            continue
        if r:
            return r
    return ('none', {})


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--cwd', default='.')
    p.add_argument('--since', default=None)
    p.add_argument('--type', dest='wf_type', default=None)
    a = p.parse_args()

    method, detail = detect(a.cwd, a.since, a.wf_type)
    print(json.dumps({'method': method,
                      'completed': method in COMPLETION_METHODS,
                      'detail': detail}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
