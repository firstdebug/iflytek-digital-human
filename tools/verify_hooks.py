#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the observable Claude hook -> JSON state path."""

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from telemetry_common import (TELEMETRY_DIR, consent_status, is_enabled,
                              load_state)

IRRELEVANT = {'Glob', 'Grep', 'TodoWrite', 'AskUserQuestion', 'WebFetch',
              'WebSearch', 'Task', 'Agent'}


def main():
    print('=' * 78)
    print('真实 hook 链路验证（JSON 状态机）')
    print('=' * 78)
    if not is_enabled():
        print('\n[!] telemetry 未开启：{}。'.format(consent_status()))
        return 1

    debug_log = TELEMETRY_DIR / 'debug.log'
    entries = []
    if debug_log.exists():
        for line in debug_log.read_text(encoding='utf-8').splitlines():
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    state = load_state()
    workflows = [x for x in state.get('workflows', []) if x.get('has_avatar_signal')]
    invocations = state.get('invocations', [])
    seen_tools = {x.get('tool_name') for x in entries if x.get('action') == 'pre'}
    leaked = seen_tools & IRRELEVANT
    prompt_entries = [x for x in entries if x.get('action') == 'prompt']
    sensitive = {'prompt_head', 'cwd', 'session_id', 'file_path'}
    leaked_fields = sorted({key for item in entries for key in sensitive if item.get(key)})
    checks = [
        ('hook 触发', bool(entries), '{} 条 debug 记录'.format(len(entries))),
        ('matcher 过滤无关工具', not leaked, '泄漏: {}'.format(sorted(leaked)) if leaked else '无泄漏'),
        ('JSON workflow 状态存在', bool(workflows), '{} workflow'.format(len(workflows))),
        ('JSON invocation 状态存在', bool(invocations), '{} invocation'.format(len(invocations))),
        ('debug 不保留原文/路径', not leaked_fields, '泄漏字段: {}'.format(leaked_fields) if leaked_fields else '无敏感字段'),
        ('pending 状态可解释', all(x.get('upload_status') in ('pending', 'uploaded', 'dead_letter')
                                     for x in workflows + invocations), '状态值合法'),
    ]
    print('\n{:<30} {:<8} {}'.format('检查项', '结果', '实际'))
    print('-' * 78)
    for name, ok, actual in checks:
        print('{:<30} {:<8} {}'.format(name, 'PASS' if ok else 'FAIL', actual))
    print('\nworkflows:')
    for item in workflows[-20:]:
        print('  {} status={} type={} revision={} upload={}'.format(
            item.get('workflow_id'), item.get('status'), item.get('workflow_type') or '-',
            item.get('revision'), item.get('upload_status')))
    print('\ninvocations:')
    for item in invocations[-20:]:
        print('  {} skill={} source={} revision={} upload={}'.format(
            item.get('invocation_id'), item.get('skill_name'), item.get('source'),
            item.get('revision'), item.get('upload_status')))
    failed = sum(not ok for _, ok, _ in checks)
    print('\n汇总: {} 通过 / {} 失败'.format(len(checks) - failed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
