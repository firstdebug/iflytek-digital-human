#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared JSON-state telemetry helpers.

Every mutation uses a short-lived file lock and temp-file replacement. The
hook path remains standard-library-only and telemetry failures stay isolated
from the agent response path.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_NAME = 'iflytek-digital-human'
LEGACY_PLUGIN_NAME = 'avatar-platform'
PLUGIN_VERSION = '1.1.0'
PLUGIN_VERSION_FILES = (
    '.claude-plugin/plugin.json',
    '.codex-plugin/plugin.json',
    '.cursor-plugin/plugin.json',
    'plugin.json',
    'package.json',
)


def _resolve_telemetry_dir(runtime_home):
    """Copy legacy local state once so consent and pending work survive rename."""
    current = Path(runtime_home) / PLUGIN_NAME / 'telemetry'
    legacy = Path(runtime_home) / LEGACY_PLUGIN_NAME / 'telemetry'
    if current.exists() or not legacy.is_dir():
        return current
    try:
        current.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(legacy), str(current))
    except FileExistsError:
        pass
    except OSError:
        return legacy
    return current if current.is_dir() else legacy


TELEMETRY_DIR = _resolve_telemetry_dir(Path.home() / '.claude')
STATE_PATH = TELEMETRY_DIR / 'state.json'
STATE_BACKUP_PATH = TELEMETRY_DIR / 'state.backup.json'
STATE_LOCK_PATH = TELEMETRY_DIR / 'state.lock'
CONSENT_PATH = TELEMETRY_DIR / 'consent.json'
CURRENT_SESSION_PATH = TELEMETRY_DIR / 'current_session'
PRIVACY_NOTICE_PATH = (Path(__file__).resolve().parent.parent / 'config' /
                       'privacy_notice.json')
GATE_CONSENT_PATH = Path(os.environ.get(
    'IFLYTEK_DIGITAL_HUMAN_GATE_CONSENT_PATH') or
    (Path.cwd() / '.runtime' / 'gate-consent.json'))

SCHEMA_VERSION = '2.0-json'
GATE_SCHEMA_VERSION = 1
NOTICE_VERSION = '2.2'
DEFAULT_AGENT_NAME = 'claude'
SESSION_REQUEST_METRICS = ('platform_ok', 'telemetry_post',
                           'telemetry_post_fail')
MAX_SESSION_REQUEST_STATS = 20


def _normalize_agent_name(value):
    if not value:
        return None
    name = str(value).strip().lower().replace(' ', '-').replace('_', '-')
    aliases = {
        'claude-code': 'claude',
        'claude': 'claude',
        'cursor-ide': 'cursor',
        'cursor': 'cursor',
        'codex-desktop': 'codex',
        'codex': 'codex',
        'aistudio': 'astudio',
        'ai-studio': 'astudio',
        'astudio': 'astudio',
        'a-studio': 'astudio',
    }
    name = aliases.get(name, name)
    if re.fullmatch(r'[a-z][a-z0-9-]{0,31}', name):
        return name
    return None


def detect_agent_name(default_name):
    for key in ('IFLYTEK_DIGITAL_HUMAN_AGENT',
                'AVATAR_PLATFORM_AGENT'):
        agent = _normalize_agent_name(os.environ.get(key))
        if agent:
            return agent

    env_keys = {key.upper() for key in os.environ}
    if any('ASTUDIO' in key or 'AISTUDIO' in key for key in env_keys):
        return 'astudio'
    return default_name


AGENT_NAME = detect_agent_name(DEFAULT_AGENT_NAME)

#获取当前时间
def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

#写入json文件,path:目标文件路径 value：要写成Json的对象，原子写入Json文件，保证文件永远不会出现不完整的Json对象
def atomic_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with open(str(tmp), 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp), str(path))
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass

def resolve_cookie_file(override=None):
    """Resolve the local Xunfei cookie path without importing browser code."""
    configured = override if override is not None else os.environ.get(
        'XFYUN_AVATAR_COOKIE_FILE')
    if configured:
        return Path(os.path.expandvars(os.path.expanduser(configured))).resolve()
    return Path(__file__).resolve().parent.parent / '.runtime' / 'xfyun_cookies.json'


def load_xfyun_auth():
    """Return the two local Cookie values required by Xunfei SSO."""
    try:
        value = json.loads(resolve_cookie_file().read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(value, dict):
        return None
    account_id = str(value.get('account_id') or '')
    session_id = str(value.get('ssoSessionId') or '')
    if (account_id and session_id and
            not re.search(r'[\x00-\x20\x7f;,]', account_id) and
            not re.search(r'[\x00-\x20\x7f;,]', session_id)):
        return {'account_id': account_id, 'ssoSessionId': session_id}
    return None


def load_xfyun_login():
    """Return account_id only when both account_id and ssoSessionId exist."""
    auth = load_xfyun_auth()
    return auth['account_id'] if auth else None


def can_upload(endpoint=None):
    return is_enabled(endpoint) and load_xfyun_login() is not None

#加载隐私政策
def load_privacy_notice():
    try:
        value = json.loads(PRIVACY_NOTICE_PATH.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

#给通知对象生成一个稳定的sha256指纹摘要
def _notice_digest(notice):
    encoded = json.dumps(notice, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()

#读取同意状态
def _read_consent():
    try:
        value = json.loads(CONSENT_PATH.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except Exception:
        return None

#获取同意状态
def consent_status():
    consent = _read_consent()
    if consent is not None and not consent.get('accepted'):
        return 'declined'
    notice = load_privacy_notice()
    if consent is None:
        return 'undecided'
    if (notice.get('notice_version') != NOTICE_VERSION or
            consent.get('notice_version') != NOTICE_VERSION or
            consent.get('notice_digest') != _notice_digest(notice)):
        return 'stale'
    return 'accepted'

#判断是否启用，endpoint:上传端点，如果不同意，则返回False，如果同意，则返回True
def is_enabled(endpoint=None):
    if consent_status() != 'accepted':
        return False
    if endpoint is not None:
        expected = load_privacy_notice().get('upload_endpoint', '').rstrip('/')
        return endpoint.rstrip('/') == expected
    return True


def write_gate_consent(status=None, path=None):
    """Write the visible workflow gate credential for accepted/declined states."""
    resolved = status or consent_status()
    if resolved not in ('accepted', 'declined'):
        return False, resolved
    target = Path(path) if path else GATE_CONSENT_PATH
    atomic_write_json(target, {
        'schema_version': GATE_SCHEMA_VERSION,
        'consent': resolved,
        'recorded_at': now_iso(),
        'source': 'telemetry-cli',
    })
    return True, resolved


def validate_gate_consent(path=None):
    """Validate the workflow gate credential against current consent state."""
    target = Path(path) if path else GATE_CONSENT_PATH
    try:
        value = json.loads(target.read_text(encoding='utf-8'))
    except Exception:
        return False, 'missing'
    if not isinstance(value, dict):
        return False, 'malformed'
    if value.get('schema_version') != GATE_SCHEMA_VERSION:
        return False, 'schema_version_invalid'
    recorded = value.get('consent')
    if recorded not in ('accepted', 'declined'):
        return False, 'consent_invalid'
    if value.get('source') != 'telemetry-cli':
        return False, 'source_invalid'
    try:
        datetime.fromisoformat(
            str(value.get('recorded_at')).replace('Z', '+00:00'))
    except Exception:
        return False, 'recorded_at_invalid'
    current = consent_status()
    if current != recorded:
        return False, 'inconsistent_status'
    return True, recorded

#获取同意状态元数据
def consent_metadata(endpoint=None):
    if not is_enabled(endpoint):
        return None
    consent = _read_consent() or {}
    return {
        'privacyNoticeVersion': consent.get('notice_version'),
        'consentedAt': consent.get('decided_at'),
    }

#获取文件锁，path:锁文件路径，timeout:超时时间，如果获取锁失败，则返回False，如果获取锁成功，则返回True
@contextmanager
def file_lock(path, timeout=2.0):
    """Acquire a portable lock and yield False if the timeout expires."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(str(path), 'a+b')
    locked = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        deadline = time.monotonic() + max(float(timeout), 0.0)
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except (OSError, IOError):
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.01)
        yield locked
    finally:
        try:
            if locked:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (OSError, IOError):
            pass
        handle.close()


#获取空状态
def _empty_state():
    return {
        'schema_version': SCHEMA_VERSION,
        'workflows': [],
        'invocations': [],
        'session_workflows': {},
        'session_request_stats': {},
        'upload': {
            'retry_count': 0,
            'last_attempt': None,
            'last_ack_at': None,
        },
    }


#规范化状态，value:要规范化的状态对象
def _normalize_state(value):
    state = _empty_state()
    if isinstance(value, dict):
        for key in ('workflows', 'invocations', 'session_workflows',
                    'session_request_stats'):
            if key in value:
                state[key] = value[key]
        if isinstance(value.get('upload'), dict):
            state['upload'].update(value['upload'])
    state['schema_version'] = SCHEMA_VERSION
    workflows = state.get('workflows')
    invocations = state.get('invocations')
    state['workflows'] = ([item for item in workflows
                           if isinstance(item, dict) and item.get('workflow_id')]
                          if isinstance(workflows, list) else [])
    state['invocations'] = ([item for item in invocations
                             if isinstance(item, dict) and item.get('invocation_id')]
                            if isinstance(invocations, list) else [])
    # Protocol 1.4 no longer collects prompt text or per-read hit counters.
    for item in state['workflows']:
        item.pop('first_prompt', None)
        item.pop('anonymous_id', None)
        item['agent'] = item.get('agent') or AGENT_NAME
    for item in state['invocations']:
        item.pop('hit_count', None)
        item.pop('revision', None)
        item.pop('anonymous_id', None)
        item['agent'] = item.get('agent') or AGENT_NAME
    if not isinstance(state.get('session_workflows'), dict):
        state['session_workflows'] = {}
    stats = state.get('session_request_stats')
    normalized_stats = {}
    if isinstance(stats, dict):
        for session_id, raw in stats.items():
            if not session_id or not isinstance(raw, dict):
                continue
            item = {}
            for metric in SESSION_REQUEST_METRICS:
                try:
                    item[metric] = max(0, int(raw.get(metric, 0) or 0))
                except (TypeError, ValueError):
                    item[metric] = 0
            item['updated_at'] = str(raw.get('updated_at') or '')
            normalized_stats[str(session_id)] = item
    latest = sorted(normalized_stats.items(),
                    key=lambda pair: pair[1].get('updated_at') or '',
                    reverse=True)[:MAX_SESSION_REQUEST_STATS]
    state['session_request_stats'] = dict(latest)
    return state


def stamp_xfyun_identity(state):
    """Stamp the current account id on all local rows before packaging."""
    account_id = load_xfyun_login()
    if not account_id or not isinstance(state, dict):
        return False
    changed = False
    for collection in ('workflows', 'invocations'):
        for item in state.get(collection, []):
            if item.get('xfyun_user_id') != account_id:
                item['xfyun_user_id'] = account_id
                changed = True
    return changed


def load_state():
    if not STATE_PATH.exists():
        return _empty_state()
    try:
        return _normalize_state(json.loads(STATE_PATH.read_text(encoding='utf-8')))
    except Exception:
        try:
            suffix = datetime.now().strftime('%Y%m%d%H%M%S%f')
            STATE_PATH.replace(STATE_PATH.with_name('state.corrupt-' + suffix + '.json'))
        except Exception:
            pass
        try:
            if STATE_BACKUP_PATH.exists():
                backup = json.loads(STATE_BACKUP_PATH.read_text(encoding='utf-8'))
                if isinstance(backup, dict):
                    return _normalize_state(backup)
        except Exception:
            pass
        return _empty_state()


def save_state(state):
    value = _normalize_state(state)
    value['updated_at'] = now_iso()
    atomic_write_json(STATE_PATH, value)
    # Keep the latest known-good snapshot for recovery from external edits or
    # interrupted writes. The copy is replaced atomically after state.json is
    # already valid, so a failed backup never affects the primary state.
    tmp = STATE_BACKUP_PATH.with_name('.' + STATE_BACKUP_PATH.name + '.' +
                                      uuid.uuid4().hex + '.tmp')
    try:
        shutil.copyfile(str(STATE_PATH), str(tmp))
        os.replace(str(tmp), str(STATE_BACKUP_PATH))
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return value


@contextmanager
def locked_state(timeout=2.0):
    with file_lock(STATE_LOCK_PATH, timeout=timeout) as acquired:
        if not acquired:
            yield None
            return
        state = load_state()
        yield state
        if state is not None:
            save_state(state)


def clear_local_telemetry():
    try:
        if not TELEMETRY_DIR.exists():
            return
        for path in TELEMETRY_DIR.iterdir():
            if (path == CONSENT_PATH or path.suffix == '.lock'
                    or not path.is_file()):
                continue
            try:
                path.unlink()
            except Exception:
                pass
    except Exception:
        pass


def set_consent(accepted):
    notice = load_privacy_notice()
    if accepted and notice.get('notice_version') != NOTICE_VERSION:
        return False, 'undecided'
    previous = _read_consent()
    if not accepted:
        atomic_write_json(CONSENT_PATH, {
            'accepted': False,
            'notice_version': notice.get('notice_version', NOTICE_VERSION),
            'decided_at': now_iso(),
        })
        clear_local_telemetry()
        return False, 'declined'
    digest = _notice_digest(notice)
    current = bool(previous and previous.get('accepted') and
                   previous.get('notice_version') == NOTICE_VERSION and
                   previous.get('notice_digest') == digest)
    if not current:
        clear_local_telemetry()
    atomic_write_json(CONSENT_PATH, {
        'accepted': True,
        'notice_version': NOTICE_VERSION,
        'notice_digest': digest,
        'decided_at': now_iso(),
    })
    return True, 'accepted'


def workflow_id_for(session_id):
    return 'wf_' + (session_id or uuid.uuid4().hex)


def next_workflow_id(session_id):
    base = workflow_id_for(session_id)
    return '{}_{}'.format(base[:54], uuid.uuid4().hex[:8])


def active_workflow_id(state, session_id):
    if session_id:
        item = state.get('session_workflows', {}).get(session_id)
        if isinstance(item, dict) and item.get('workflow_id'):
            return item['workflow_id']
    return workflow_id_for(session_id)


def set_active_workflow(state, session_id, workflow_id):
    if session_id:
        state.setdefault('session_workflows', {})[session_id] = {
            'workflow_id': workflow_id,
            'updated_at': now_iso(),
        }


_LOCAL_PATH_RE = re.compile(
    r'(?i)(?:[a-z]:[\\/]|\\\\)[^\s,;"]+'
    r'|(?<![:\w])/(?:home|users|tmp|var|opt|private|mnt)/[^\s,;"]+'
)


def _sanitize_detail_value(value):
    if isinstance(value, dict):
        return sanitize_completion_detail(value)
    if isinstance(value, list):
        return [_sanitize_detail_value(item) for item in value]
    if isinstance(value, str):
        return _LOCAL_PATH_RE.sub('[local_path]', value)
    return value


def sanitize_completion_detail(detail):
    if not isinstance(detail, dict):
        return {}
    sensitive = ('password', 'token', 'secret', 'apikey', 'api_key',
                 'cookie', 'authorization', 'ssosessionid', 'session_id')
    return {key: _sanitize_detail_value(value)
            for key, value in detail.items()
            if key not in ('source', 'path', 'cwd', 'file_path') and
            not any(part in str(key).lower().replace('-', '_')
                    for part in sensitive)}


def plugin_root():
    value = (os.environ.get('IFLYTEK_DIGITAL_HUMAN_PLUGIN_ROOT') or
             os.environ.get('CLAUDE_PLUGIN_ROOT'))
    return Path(value) if value else Path(__file__).resolve().parent.parent


def _candidate_plugin_roots():
    bases = [
        os.environ.get('IFLYTEK_DIGITAL_HUMAN_PLUGIN_ROOT'),
        os.environ.get('CLAUDE_PLUGIN_ROOT'),
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path.cwd(),
    ]
    seen = set()
    for base in bases:
        if not base:
            continue
        try:
            path = Path(base).expanduser()
        except TypeError:
            continue
        for depth, candidate in enumerate((path, *path.parents)):
            if depth > 6:
                break
            try:
                key = str(candidate.resolve(strict=False)).lower()
            except Exception:
                key = str(candidate).lower()
            if key in seen:
                continue
            seen.add(key)
            yield candidate


def _read_plugin_version(path):
    try:
        meta = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    version = meta.get('version')
    if isinstance(version, str) and version.strip():
        return version.strip()
    return None


def plugin_version():
    override = (os.environ.get('IFLYTEK_DIGITAL_HUMAN_PLUGIN_VERSION') or
                os.environ.get('AVATAR_PLATFORM_PLUGIN_VERSION'))
    if override and override.strip():
        return override.strip()
    for root in _candidate_plugin_roots():
        for relative in PLUGIN_VERSION_FILES:
            version = _read_plugin_version(root / relative)
            if version:
                return version
    return PLUGIN_VERSION


def read_current_session():
    try:
        value = json.loads(CURRENT_SESSION_PATH.read_text(encoding='utf-8'))
        return value.get('session_id'), value.get('cwd')
    except Exception:
        return None, None


def write_current_session(session_id, cwd=None):
    if not session_id:
        return
    try:
        previous_sid, previous_cwd = read_current_session()
        if not cwd and previous_sid == session_id:
            cwd = previous_cwd
        payload = {'session_id': session_id, 'at': now_iso()}
        if cwd:
            payload['cwd'] = cwd
        atomic_write_json(CURRENT_SESSION_PATH, payload)
    except Exception:
        pass


def increment_session_request(metric, session_id=None):
    """Increment one local-only request counter for the current Claude session."""
    if metric not in SESSION_REQUEST_METRICS:
        return False
    if not session_id:
        session_id, _ = read_current_session()
    if not session_id:
        return False
    try:
        with locked_state() as state:
            if state is None:
                return False
            stats = state.setdefault('session_request_stats', {})
            item = stats.setdefault(str(session_id), {
                name: 0 for name in SESSION_REQUEST_METRICS
            })
            item[metric] = int(item.get(metric, 0) or 0) + 1
            item['updated_at'] = now_iso()
        return True
    except Exception:
        return False


def spawn_uploader(force=False):
    if not can_upload():
        return False
    try:
        uploader = Path(__file__).resolve().parent / 'uploader.py'
        args = [sys.executable, str(uploader)] + (['--force'] if force else [])
        kwargs = {
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL,
            'start_new_session': os.name != 'nt',
        }
        if os.name == 'nt':
            kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        subprocess.Popen(args, **kwargs)
        return True
    except Exception:
        return False
