#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claude hooks for iflytek-digital-human JSON-state telemetry.

Business facts are persisted locally. Upload is triggered only by the
authenticated xfyun_common login/session path; failures never block the agent.
"""

import json
import os
import re
import sys

from avatar_intent import explicit_avatar_commands

_TM_DIR = os.path.join(os.path.expanduser('~'), '.claude', 'iflytek-digital-human',
                       'telemetry')
_DEBUG_MARK = os.path.join(_TM_DIR, 'debug')
_DEBUG_LOG = os.path.join(_TM_DIR, 'debug.log')


def _debug(action, payload, relevant=None):
    try:
        if not os.path.exists(_DEBUG_MARK):
            return
        entry = {
            'action': action,
            'tool_name': payload.get('tool_name'),
            'relevant': relevant,
            'has_cwd': bool(payload.get('cwd')),
            'payload_keys': sorted(payload.keys()),
        }
        with open(_DEBUG_LOG, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass


SKILL_RESOURCE_RE = re.compile(
    r'(?:^|[/\\])skills[/\\]([a-z0-9][a-z0-9-]*)[/\\]'
    r'(?:skill\.md|(?:references|scripts|templates|assets)[/\\].+)$', re.I)
CURRENT_PLUGIN_ROOT = os.path.normcase(os.path.realpath(
    os.path.join(os.path.dirname(__file__), os.pardir)))
PATHY_RE = re.compile(
    r'[A-Za-z]:[\\/][^\s"\']*|~?/[^\s"\']{3,}|https?://\S+|`[^`]*`', re.I)

ENTRY_SKILLS = {'avatar-workflow-entry', 'iflytek-digital-human'}
TYPE_HINTS = {
    'avatar-verification': 'sdk_integration',
    'avatar-credentials': 'credentials_setup',
    'avatar-model-config': 'model_config',
    'avatar-web-template': 'web_template',
    'avatar-live-streaming': 'live_streaming',
    'avatar-webapi-protocol': 'webapi_protocol',
    'avatar-knowledge-base': 'knowledge_base',
    'avatar-troubleshoot': 'troubleshoot',
    'avatar-config-authoring': 'config_authoring',
    'avatar-executing': 'sdk_integration',
    'avatar-planning': 'sdk_integration',
    'avatar-brainstorming': 'sdk_integration',
}
PRIMARY_SKILLS = {
    'avatar-live-streaming', 'avatar-web-template', 'avatar-webapi-protocol',
    'avatar-executing', 'avatar-planning', 'avatar-brainstorming',
}
AUXILIARY_TYPES = {
    'credentials_setup', 'model_config', 'knowledge_base', 'troubleshoot',
    'config_authoring',
}
COMPLETION_METHODS = ('verification_flag', 'artifact', 'artifacts_file')
RESUME_WINDOW_MINUTES = 5
STALE_MINUTES = 30
RELEVANT_TOOLS = {'Read'}


def _is_current_plugin_resource(file_path):
    try:
        candidate = os.path.normcase(os.path.realpath(file_path))
        return os.path.commonpath((candidate, CURRENT_PLUGIN_ROOT)) == CURRENT_PLUGIN_ROOT
    except (TypeError, ValueError):
        return False


def _workflow(state, workflow_id):
    return next((item for item in state.get('workflows', [])
                 if item.get('workflow_id') == workflow_id), None)


def _invocation(state, workflow_id, skill_name):
    return next((item for item in state.get('invocations', [])
                 if item.get('workflow_id') == workflow_id and
                 item.get('skill_name') == skill_name), None)


def _touch_workflow(item, **changes):
    changed = False
    for key, value in changes.items():
        if item.get(key) != value:
            item[key] = value
            changed = True
    if changed:
        from telemetry_common import now_iso
        item['revision'] = int(item.get('revision') or 0) + 1
        item['upload_status'] = 'pending'
        item['updated_at'] = now_iso()
    return changed


def _parse_iso(value):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def _latest_activity(state, item):
    values = [item.get('ended_at'), item.get('updated_at'), item.get('started_at')]
    for mapping in state.get('session_workflows', {}).values():
        if isinstance(mapping, dict) and mapping.get('workflow_id') == item.get('workflow_id'):
            values.append(mapping.get('updated_at'))
    parsed = [value for value in (_parse_iso(v) for v in values) if value]
    return max(parsed) if parsed else None


def _normalized_cwd(value):
    if not value:
        return None
    try:
        return os.path.normcase(os.path.realpath(value))
    except (TypeError, ValueError, OSError):
        return None


def _is_generic_cwd(cwd):
    return _normalized_cwd(cwd) == _normalized_cwd(os.path.expanduser('~'))


def _should_refine_cwd(previous, current):
    old = _normalized_cwd(previous)
    new = _normalized_cwd(current)
    if not old or not new or old == new:
        return False
    try:
        if os.path.commonpath((new, CURRENT_PLUGIN_ROOT)) == CURRENT_PLUGIN_ROOT:
            return False
        return os.path.commonpath((old, new)) == old
    except ValueError:
        return False


def _find_resumable(state, cwd):
    """Find a recent unfinished workflow matching cwd and the resume window."""
    if not cwd or _is_generic_cwd(cwd):
        return None
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=RESUME_WINDOW_MINUTES)
    candidates = []
    for item in state.get('workflows', []):
        if item.get('cwd') != cwd:
            continue
        ordinary = (not item.get('completion_method') and
                    item.get('status') == 'interrupted')
        activity = _latest_activity(state, item)
        if ordinary and activity and activity > cutoff:
            candidates.append(item)
    candidates.sort(key=lambda item: item.get('started_at') or '', reverse=True)
    return candidates[0].get('workflow_id') if candidates else None


def _resume_workflow(item, clear_completion=False):
    changes = {'status': 'in_progress', 'ended_at': None}
    if clear_completion:
        changes.update(completion_method=None, completion_detail=None)
    return _touch_workflow(item, **changes)


def _insert_workflow(state, workflow_id, cwd, workflow_type=None):
    from telemetry_common import AGENT_NAME, load_xfyun_login, now_iso, plugin_version
    stamp = now_iso()
    item = {
        'workflow_id': workflow_id,
        'workflow_type': workflow_type,
        'agent': AGENT_NAME,
        'xfyun_user_id': load_xfyun_login(),
        'started_at': stamp,
        'ended_at': None,
        'status': 'in_progress',
        'has_avatar_signal': 1,
        'completion_method': None,
        'completion_detail': None,
        'os': sys.platform,
        'plugin_version': plugin_version(),
        'revision': 1,
        'cwd': cwd,
        'upload_status': 'pending',
        'updated_at': stamp,
    }
    state.setdefault('workflows', []).append(item)
    return item


def ensure_workflow(state, workflow_id, signal=False, cwd=None, session_id=None):
    from telemetry_common import next_workflow_id, set_active_workflow
    item = _workflow(state, workflow_id)
    invalid_sdk = bool(item and item.get('status') == 'completed' and
                       item.get('workflow_type') == 'sdk_integration' and
                       item.get('completion_method') != 'verification_flag')
    if invalid_sdk:
        _resume_workflow(item, clear_completion=True)
        set_active_workflow(state, session_id, workflow_id)

    terminal = bool(item and item.get('status') in
                    ('completed', 'failed', 'cancelled'))
    if terminal:
        workflow_id = next_workflow_id(session_id)
        item = None

    if item is None:
        if not signal:
            return None
        previous_id = None if terminal else _find_resumable(state, cwd)
        if previous_id:
            previous = _workflow(state, previous_id)
            _resume_workflow(previous, clear_completion=True)
            set_active_workflow(state, session_id, previous_id)
            return previous_id
        _insert_workflow(state, workflow_id, cwd)
        set_active_workflow(state, session_id, workflow_id)
        return workflow_id

    if signal and not item.get('has_avatar_signal'):
        _touch_workflow(item, has_avatar_signal=1)
    if signal and _should_refine_cwd(item.get('cwd'), cwd):
        _touch_workflow(item, cwd=cwd)
    if signal:
        set_active_workflow(state, session_id, workflow_id)
    return workflow_id


def maybe_set_type(state, workflow_id, skill):
    item = _workflow(state, workflow_id)
    if not item or item.get('workflow_type') or skill.lower() in ENTRY_SKILLS:
        return
    workflow_type = TYPE_HINTS.get(skill.lower())
    if workflow_type:
        _touch_workflow(item, workflow_type=workflow_type)


def record_invocation(state, workflow_id, skill, source):
    """Record business usage once per workflow and skill."""
    if _invocation(state, workflow_id, skill):
        return False
    import uuid
    from telemetry_common import AGENT_NAME, load_xfyun_login, now_iso
    stamp = now_iso()
    state.setdefault('invocations', []).append({
        'invocation_id': 'inv_' + uuid.uuid4().hex[:16],
        'workflow_id': workflow_id,
        'skill_name': skill,
        'agent': AGENT_NAME,
        'xfyun_user_id': load_xfyun_login(),
        'source': source,
        'first_at': stamp,
        'last_at': stamp,
        'upload_status': 'pending',
        'updated_at': stamp,
    })
    maybe_set_type(state, workflow_id, skill)
    return True


def route_workflow_for_skill(state, workflow_id, session_id, skill, cwd):
    if skill.lower() not in PRIMARY_SKILLS:
        return workflow_id
    target_type = TYPE_HINTS.get(skill.lower())
    if not target_type:
        return workflow_id
    item = _workflow(state, workflow_id)
    if not item:
        return workflow_id
    current_type = item.get('workflow_type')
    if not current_type:
        _touch_workflow(item, workflow_type=target_type)
        return workflow_id
    if current_type == target_type or item.get('status') != 'in_progress':
        return workflow_id
    if current_type in AUXILIARY_TYPES:
        _touch_workflow(item, workflow_type=target_type)
        return workflow_id
    from telemetry_common import next_workflow_id, now_iso, set_active_workflow
    _touch_workflow(item, status='cancelled', ended_at=now_iso())
    new_id = next_workflow_id(session_id)
    _insert_workflow(state, new_id, item.get('cwd') or cwd,
                     workflow_type=target_type)
    set_active_workflow(state, session_id, new_id)
    return new_id


def handle_pre(state, payload, workflow_id, session_id=None):
    tool = payload.get('tool_name') or ''
    tool_input = payload.get('tool_input') or {}
    if tool == 'Read':
        path = tool_input.get('file_path') or ''
        if not _is_current_plugin_resource(path):
            return workflow_id
        match = SKILL_RESOURCE_RE.search(path)
        if match:
            skill = match.group(1).lower()
            workflow_id = ensure_workflow(
                state, workflow_id, signal=True, cwd=payload.get('cwd'),
                session_id=session_id) or workflow_id
            workflow_id = route_workflow_for_skill(
                state, workflow_id, session_id, skill, cwd=payload.get('cwd'))
            record_invocation(state, workflow_id, skill, source='read')
    return workflow_id


def resolve_completion(payload, started_at, workflow_type, existing_method,
                       workflow_cwd=None):
    if existing_method in COMPLETION_METHODS:
        return existing_method, {}
    try:
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
        from completion_check import detect
        return detect(workflow_cwd or payload.get('cwd') or '.', started_at,
                      workflow_type)
    except Exception:
        return 'none', {}


def decide_final_status(status, method, detail):
    if status in ('completed', 'failed', 'cancelled'):
        return status
    if detail.get('failed'):
        return 'failed'
    if method in COMPLETION_METHODS:
        return 'completed'
    return 'interrupted' if status == 'in_progress' else status


def opportunistic_scan(state, workflow_id, payload):
    item = _workflow(state, workflow_id)
    if not item or item.get('completion_method'):
        return False
    cwd = item.get('cwd') or payload.get('cwd')
    if not cwd:
        return False
    method, detail = resolve_completion(
        payload, item.get('started_at'), item.get('workflow_type'), None, cwd)
    if method == 'none':
        return False
    from telemetry_common import now_iso, sanitize_completion_detail
    clean = sanitize_completion_detail(detail)
    if method in COMPLETION_METHODS:
        final = 'failed' if detail.get('failed') else 'completed'
        return _touch_workflow(
            item, completion_method=method, completion_detail=clean,
            status=final, ended_at=now_iso())
    return _touch_workflow(item, completion_method=method,
                           completion_detail=clean)


def reconcile_stale(state, current_workflow_id):
    from datetime import datetime, timedelta, timezone
    from telemetry_common import now_iso
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)
    changed = False
    for item in state.get('workflows', []):
        if (item.get('workflow_id') == current_workflow_id or
                item.get('status') != 'in_progress'):
            continue
        activity = _latest_activity(state, item)
        if not activity or activity >= cutoff:
            continue
        final = ('completed' if item.get('completion_method') in
                 COMPLETION_METHODS else 'interrupted')
        changed = _touch_workflow(
            item, status=final, ended_at=now_iso()) or changed
    return changed


def handle_prompt(state, payload, workflow_id, session_id=None):
    prompt = payload.get('prompt') or payload.get('user_prompt') or ''
    skills = explicit_avatar_commands(prompt)
    if skills:
        workflow_id = ensure_workflow(
            state, workflow_id, signal=True, cwd=payload.get('cwd'),
            session_id=session_id) or workflow_id
        for skill in skills:
            skill = skill.lower()
            workflow_id = route_workflow_for_skill(
                state, workflow_id, session_id, skill, cwd=payload.get('cwd'))
            record_invocation(state, workflow_id, skill, source='slash')
    item = _workflow(state, workflow_id)
    if item:
        from telemetry_common import set_active_workflow
        set_active_workflow(state, session_id, workflow_id)
        reconcile_stale(state, workflow_id)
        opportunistic_scan(state, workflow_id, payload)
        return workflow_id
    return None


def handle_end(state, payload, workflow_id):
    item = _workflow(state, workflow_id)
    if not item:
        return False
    from telemetry_common import now_iso, sanitize_completion_detail
    method, detail = resolve_completion(
        payload, item.get('started_at'), item.get('workflow_type'),
        item.get('completion_method'), item.get('cwd'))
    final = decide_final_status(item.get('status'), method, detail)
    changes = {'status': final, 'ended_at': now_iso()}
    if method != 'none' and not item.get('completion_method'):
        changes.update(completion_method=method,
                       completion_detail=sanitize_completion_detail(detail))
    return _touch_workflow(item, **changes)


def has_pending(state):
    return any(item.get('upload_status') == 'pending'
               for key in ('workflows', 'invocations')
               for item in state.get(key, []))


def _is_relevant(action, payload):
    if action != 'pre':
        return True
    tool = payload.get('tool_name') or ''
    if tool not in RELEVANT_TOOLS:
        return False
    if tool == 'Read':
        path = (payload.get('tool_input') or {}).get('file_path') or ''
        return bool(SKILL_RESOURCE_RE.search(path) and
                    _is_current_plugin_resource(path))
    return True


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ''
    if action not in ('pre', 'prompt', 'stop', 'end'):
        return
    try:
        raw = sys.stdin.buffer.read().decode('utf-8', errors='replace')
    except Exception:
        raw = sys.stdin.read()
    if not raw.strip():
        return
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return

    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
    from telemetry_common import (active_workflow_id, is_enabled, locked_state,
                                  write_current_session)
    if not is_enabled():
        return
    relevant = _is_relevant(action, payload)
    _debug(action, payload, relevant)
    if not relevant:
        return

    session_id = payload.get('session_id')
    write_current_session(session_id, payload.get('cwd'))
    # PreToolUse has a tight host timeout. Missing one telemetry write is
    # preferable to delaying or cancelling the agent's Read operation.
    lock_timeouts = (0.5,) if action == 'pre' else (2.0, 1.0)
    for lock_timeout in lock_timeouts:
        with locked_state(timeout=lock_timeout) as state:
            if state is None:
                continue
            workflow_id = active_workflow_id(state, session_id)
            if action == 'pre':
                handle_pre(state, payload, workflow_id, session_id=session_id)
            elif action == 'prompt':
                handle_prompt(state, payload, workflow_id, session_id=session_id)
            elif action == 'stop':
                opportunistic_scan(state, workflow_id, payload)
            elif action == 'end':
                handle_end(state, payload, workflow_id)
            break
    else:
        return


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
