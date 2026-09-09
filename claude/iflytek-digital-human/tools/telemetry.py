#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reporter CLI for JSON-state telemetry."""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from telemetry_common import (CONSENT_PATH, NOTICE_VERSION, STATE_PATH,
                              active_workflow_id, consent_status,
                              is_enabled, load_privacy_notice, load_state,
                              locked_state, now_iso, read_current_session,
                              sanitize_completion_detail, set_consent,
                              set_active_workflow, spawn_uploader)

COMPLETION_METHODS = ('verification_flag', 'artifact', 'artifacts_file')


def _flush_after_change(changed):
    if changed:
        spawn_uploader(force=True)


def render_privacy_notice():
    notice = load_privacy_notice()
    extras = notice.get('additional_purposes') or []
    extra = ('另用于{}。'.format('、'.join(extras))) if extras else ''
    privacy_url = notice.get('privacy_policy_url') or ''
    agreement_url = notice.get('user_agreement_url') or ''
    policies = ''
    if privacy_url or agreement_url:
        policies = (
            "本插件使用统计遵循讯飞开放平台隐私保护规定，完整条款以官方文本为准："
            "《讯飞开放平台隐私政策》{privacy}；"
            "《讯飞开放平台用户服务协议》{agreement}。"
            "请先阅读上述文件；以下仅说明本插件使用统计的额外采集范围。"
        ).format(privacy=privacy_url, agreement=agreement_url)
    return (
        "iflytek-digital-human 使用统计授权说明（声明版本：{version}）："
        "{policies}"
        "数据处理方（同时为数据接收方）为{controller}。"
        "在您明确选择[同意]后，我们将收集讯飞账号标识、使用过的 Skill 名称和来源、"
        "工作流类型与状态、时间、操作系统、插件版本以及脱敏后的完成证据，"
        "用于统计功能使用情况、分析完成率和常见中断环节、改进插件稳定性。{extra}"
        "项目目录仅在本地用于工作流接续和产物验证，不会上报；"
        "对话全文和后续 Prompt 原文不会落盘或上传；"
        "不会收集代码文件、绝对路径、密码、Cookie、Token、apiKey、apiSecret 或接口原文。"
        "数据上报至{endpoint}，存储于{region}，服务端保存{retention}天后删除或匿名化；"
        "撤回授权后将停止采集并清除本地数据。"
        "隐私联系方式为{contact}。{deletion}"
        "本地状态文件位于{state}。"
        "不同意不会影响 iflytek-digital-human 的正常功能；"
        "沉默、继续使用插件或关闭本提示均不视为同意；"
        "可随时选择[不同意]撤回授权。"
    ).format(
        version=notice.get('notice_version', NOTICE_VERSION),
        policies=policies,
        controller=notice.get('controller_name', '[待补充]'),
        extra=extra,
        endpoint=notice.get('upload_endpoint', '[待补充]'),
        region=notice.get('storage_region', '[待补充]'),
        retention=notice.get('retention_days', 365),
        contact=notice.get('contact', '[待补充]'),
        deletion=notice.get('server_deletion_method', ''),
        state=STATE_PATH,
    )


def _resolve_session(session_id):
    current_sid, cwd = read_current_session()
    if session_id:
        return session_id, cwd if current_sid == session_id else None
    return current_sid, cwd or os.getcwd()


def _bump(item, **changes):
    changed = False
    for key, value in changes.items():
        if item.get(key) != value:
            item[key] = value
            changed = True
    if changed:
        item['revision'] = int(item.get('revision') or 0) + 1
        item['upload_status'] = 'pending'
        item['updated_at'] = now_iso()
    return changed


def _find_workflow(state, workflow_id):
    return next((item for item in state.get('workflows', [])
                 if item.get('workflow_id') == workflow_id), None)


def _find_unique_in_progress_workflow(state, workflow_type=None):
    """Resolve a missing session only when attribution is unambiguous."""
    active = [item for item in state.get('workflows', [])
              if item.get('status') == 'in_progress']
    if workflow_type:
        active = [item for item in active
                  if item.get('workflow_type') in (None, workflow_type)]
    if len(active) == 1:
        return active[0], None
    return None, 'no_workflow_row' if not active else 'ambiguous_workflow'


def _find_workflow_for_project(state, project_dir):
    """Resolve a project completion without using global session state.

    Hooks can briefly record a project subdirectory (for example the SDK's
    ``esm`` folder) as cwd.  A completion report is still scoped to the
    requested project, so descendant cwd records are eligible; an ancestor
    cwd record is deliberately not eligible because it could belong to an
    unrelated project.
    """
    project = os.path.normcase(os.path.realpath(str(Path(project_dir))))
    exact = []
    descendants = []
    for item in state.get('workflows', []):
        value = item.get('cwd')
        if not value:
            continue
        candidate = os.path.normcase(os.path.realpath(str(value)))
        if candidate == project:
            exact.append(item)
            continue
        try:
            if os.path.commonpath((project, candidate)) == project:
                descendants.append(item)
        except ValueError:
            continue
    scoped = exact + descendants
    active = [item for item in scoped if item.get('status') == 'in_progress']
    if len(active) == 1:
        return active[0]
    if active:
        return None
    if len(exact) == 1:
        return exact[0]
    if len(descendants) == 1:
        return descendants[0]
    return None


def _update_status(session_id, status, workflow_type=None, reason=None,
                   verify=True, project_dir=None):
    if not is_enabled():
        return False, 'disabled'
    # A project-scoped report must not fall back to the process-global
    # current_session file; concurrent Claude sessions can overwrite it.
    sid, cwd = _resolve_session(session_id)
    # A project-scoped report must be resolved from its project path, never
    # from the process-global current_session pointer.
    if project_dir and not session_id:
        sid = None
    if project_dir:
        cwd = str(Path(project_dir).resolve())
    with locked_state() as state:
        if state is None:
            return False, 'state_lock_timeout'
        missing_reason = None
        if project_dir and not sid:
            item = _find_workflow_for_project(state, project_dir)
        elif sid:
            item = _find_workflow(state, active_workflow_id(state, sid))
        elif status == 'completed':
            item, missing_reason = _find_unique_in_progress_workflow(
                state, workflow_type)
            cwd = os.getcwd()
        else:
            return False, 'no_session'
        if not item:
            return False, (missing_reason or
                           ('ambiguous_workflow' if project_dir and not sid
                            else 'no_workflow_row'))
        workflow_id = item.get('workflow_id')
        target_type = workflow_type or item.get('workflow_type')
        method, detail = 'reported', {'self_reported': True}
        if verify and status == 'completed':
            try:
                from completion_check import detect
                detected_method, detected_detail = detect(
                    cwd or item.get('cwd') or '.', item.get('started_at'),
                    target_type)
                if detected_method != 'none':
                    method, detail = detected_method, detected_detail
            except Exception:
                pass
        terminal = item.get('status') in ('completed', 'failed', 'cancelled')
        recoverable_cancel = (
            item.get('status') == 'cancelled' and verify and
            status == 'completed' and method in COMPLETION_METHODS and
            not detail.get('failed')
        )
        if terminal and not recoverable_cancel:
            return False, 'workflow_not_in_progress'
        if (status == 'completed' and target_type == 'sdk_integration' and
                (method != 'verification_flag' or detail.get('failed'))):
            return False, 'needs_runtime_verification'
        if (status == 'completed' and target_type == 'web_template' and
                (method != 'artifacts_file' or
                 'template_url' not in (detail.get('found') or []))):
            return False, 'needs_template_artifact'
        if reason:
            detail['reason'] = reason
        detail = sanitize_completion_detail(detail)
        changes = {
            'status': status,
            'ended_at': now_iso(),
            'completion_method': method,
            'completion_detail': detail,
        }
        if workflow_type and not item.get('workflow_type'):
            changes['workflow_type'] = workflow_type
        changed = _bump(item, **changes)
    return changed, method


def report_complete(session_id=None, workflow_type=None, project_dir=None):
    changed, info = _update_status(session_id, 'completed', workflow_type,
                                   project_dir=project_dir)
    _flush_after_change(changed)
    return changed, info


def report_fail(session_id=None, reason=None, project_dir=None):
    changed, info = _update_status(session_id, 'failed', reason=reason, verify=False,
                                   project_dir=project_dir)
    _flush_after_change(changed)
    return changed, info


def report_gate(gate, gate_status, issues, session_id=None, project_dir=None):
    if not is_enabled():
        return False, 'disabled'
    sid = session_id
    if not sid and not project_dir:
        return False, 'no_session'
    detail = sanitize_completion_detail({
        'gate': str(gate),
        'gate_status': str(gate_status),
        'remaining_issues': list(issues or []),
        'recoverable': True,
    })
    with locked_state() as state:
        if state is None:
            return False, 'state_lock_timeout'
        item = (_find_workflow_for_project(state, project_dir)
                if project_dir and not sid else
                _find_workflow(state, active_workflow_id(state, sid)))
        if not item:
            return False, 'ambiguous_workflow' if project_dir and not sid else 'no_workflow_row'
        if item.get('status') != 'in_progress':
            return False, 'workflow_not_in_progress'
        changed = _bump(item, completion_detail=detail)
    _flush_after_change(changed)
    return changed, 'reported' if changed else 'unchanged'


def purge_old(days=7):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0
    with locked_state() as state:
        if state is None:
            return 0
        keep = []
        removed_ids = set()
        for item in state.get('workflows', []):
            stamp = item.get('started_at')
            parsed = None
            try:
                parsed = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
            except Exception:
                pass
            if (parsed and parsed < cutoff and
                    item.get('upload_status') in ('uploaded', 'dead_letter')):
                removed_ids.add(item.get('workflow_id'))
                removed += 1
            else:
                keep.append(item)
        state['workflows'] = keep
        state['invocations'] = [item for item in state.get('invocations', [])
                                if item.get('workflow_id') not in removed_ids]
        state['session_workflows'] = {
            key: value for key, value in state.get('session_workflows', {}).items()
            if not isinstance(value, dict) or value.get('workflow_id') not in removed_ids
        }
    return removed


def show_stats():
    state = load_state()
    session_id, _ = read_current_session()
    request_stats = state.get('session_request_stats', {})
    current = request_stats.get(session_id, {}) if session_id else {}
    print('=== 当前 Claude 会话服务端请求 ===')
    print('  session={}'.format(session_id or 'unknown'))
    print('  platform_ok={} telemetry_post={} telemetry_post_fail={}'.format(
        int(current.get('platform_ok', 0) or 0),
        int(current.get('telemetry_post', 0) or 0),
        int(current.get('telemetry_post_fail', 0) or 0)))
    recent = sorted(request_stats.items(),
                    key=lambda pair: pair[1].get('updated_at') or '',
                    reverse=True)[:5]
    if recent:
        print('  recent_sessions={}'.format(', '.join(key for key, _ in recent)))
    print()
    workflows = [item for item in state.get('workflows', [])
                 if item.get('has_avatar_signal')]
    invocations = state.get('invocations', [])
    print('=== 使用过的 Skill ===')
    counts = {}
    for item in invocations:
        counts[item.get('skill_name')] = counts.get(item.get('skill_name'), 0) + 1
    for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
        print('  {:<32} workflows={}'.format(name, count))
    print('\n=== 工作流完成情况 ===')
    for item in sorted(workflows, key=lambda x: x.get('started_at') or '', reverse=True)[:30]:
        print('  {:<22} {:<18} {:<12} {} -> {}'.format(
            item.get('workflow_id'), item.get('workflow_type') or '-',
            item.get('status'), item.get('started_at'), item.get('ended_at') or '-'))
    print('\n=== 用户总数 ===')
    print('  {}'.format(len({item.get('xfyun_user_id') for item in workflows
                             if item.get('xfyun_user_id')})))
    print('\n=== 完成率 ===')
    done = sum(item.get('status') == 'completed' for item in workflows)
    cancelled = sum(item.get('status') == 'cancelled' for item in workflows)
    denominator = len(workflows) - cancelled
    rate = '{:.1%}'.format(done / denominator) if denominator else 'n/a'
    print('  total={} completed={} ({})'.format(len(workflows), done, rate))
    print('  interrupted={} failed={} cancelled={} in_progress={}'.format(
        sum(item.get('status') == 'interrupted' for item in workflows),
        sum(item.get('status') == 'failed' for item in workflows), cancelled,
        sum(item.get('status') == 'in_progress' for item in workflows)))


def main():
    parser = argparse.ArgumentParser(prog='telemetry.py')
    sub = parser.add_subparsers(dest='cmd')
    complete = sub.add_parser('complete')
    complete.add_argument('--session', default=None)
    complete.add_argument('--type', dest='wf_type', default=None)
    complete.add_argument('--project', default=None)
    fail = sub.add_parser('fail')
    fail.add_argument('--session', default=None)
    fail.add_argument('--reason', default=None)
    fail.add_argument('--project', default=None)
    consent = sub.add_parser('consent')
    group = consent.add_mutually_exclusive_group(required=True)
    group.add_argument('--accept', action='store_true')
    group.add_argument('--decline', action='store_true')
    group.add_argument('--status', action='store_true')
    sub.add_parser('stats')
    sub.add_parser('notice')
    purge = sub.add_parser('purge')
    purge.add_argument('--days', type=int, default=7)
    args = parser.parse_args()
    if args.cmd == 'complete':
        ok, info = report_complete(args.session, args.wf_type, args.project)
        print('completed via {}'.format(info) if ok else 'skipped ({})'.format(info))
    elif args.cmd == 'fail':
        ok, info = report_fail(args.session, args.reason, args.project)
        print('marked failed' if ok else 'skipped ({})'.format(info))
    elif args.cmd == 'consent':
        if args.status:
            print(consent_status())
        else:
            accepted, reason = set_consent(args.accept)
            print('telemetry {} (notice v{}) -> {}'.format(reason, NOTICE_VERSION, CONSENT_PATH))
            if args.accept and not accepted:
                print('privacy notice is unavailable or has an invalid version')
    elif args.cmd == 'stats':
        show_stats()
    elif args.cmd == 'purge':
        print('purged {} workflows older than {} days'.format(purge_old(args.days), args.days))
    elif args.cmd == 'notice':
        print(render_privacy_notice())
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
