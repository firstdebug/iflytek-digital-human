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
import platform
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

TELEMETRY_DIR = Path.home() / '.claude' / 'avatar-grill' / 'telemetry'
STATE_PATH = TELEMETRY_DIR / 'state.json'
STATE_LOCK_PATH = TELEMETRY_DIR / 'state.lock'
ANON_ID_PATH = TELEMETRY_DIR / 'anonymous_id.json'
CONSENT_PATH = TELEMETRY_DIR / 'consent.json'
CURRENT_SESSION_PATH = TELEMETRY_DIR / 'current_session'
PRIVACY_NOTICE_PATH = (Path(__file__).resolve().parent.parent / 'config' /
                       'privacy_notice.json')

SCHEMA_VERSION = '2.0-json'
NOTICE_VERSION = '2.1'


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def _machine_id_windows():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r'SOFTWARE\Microsoft\Cryptography')
        try:
            value, _ = winreg.QueryValueEx(key, 'MachineGuid')
            return value
        finally:
            winreg.CloseKey(key)
    except Exception:
        return None


def _machine_id_darwin():
    try:
        out = subprocess.run(
            ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
            capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if 'IOPlatformUUID' in line:
                return line.split('"')[-2]
    except Exception:
        pass
    return None


def _machine_id_linux():
    for name in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        try:
            value = Path(name).read_text(encoding='utf-8').strip()
            if value:
                return value
        except Exception:
            continue
    return None


def _raw_machine_id():
    system = platform.system()
    if system == 'Windows':
        return _machine_id_windows(), 'windows_machineguid'
    if system == 'Darwin':
        return _machine_id_darwin(), 'macos_platform_uuid'
    return _machine_id_linux(), 'linux_machine_id'


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


def resolve_anonymous_id():
    try:
        if ANON_ID_PATH.exists():
            value = json.loads(ANON_ID_PATH.read_text(encoding='utf-8'))
            if isinstance(value, dict) and value.get('anonymous_id'):
                return value['anonymous_id']
    except Exception:
        pass
    raw = _raw_machine_id()[0]
    if raw:
        digest = hashlib.sha256(str(raw).encode('utf-8')).hexdigest()[:16]
    else:
        digest = uuid.uuid4().hex[:16]
    anonymous_id = 'anon_' + digest
    try:
        atomic_write_json(ANON_ID_PATH, {'anonymous_id': anonymous_id})
    except Exception:
        pass
    return anonymous_id


def get_anonymous_id():
    with file_lock(STATE_LOCK_PATH, timeout=2.0):
        return resolve_anonymous_id()


def load_privacy_notice():
    try:
        value = json.loads(PRIVACY_NOTICE_PATH.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _notice_digest(notice):
    encoded = json.dumps(notice, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _read_consent():
    try:
        value = json.loads(CONSENT_PATH.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


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


def is_enabled(endpoint=None):
    if consent_status() != 'accepted':
        return False
    if endpoint is not None:
        expected = load_privacy_notice().get('upload_endpoint', '').rstrip('/')
        return endpoint.rstrip('/') == expected
    return True


def consent_metadata(endpoint=None):
    if not is_enabled(endpoint):
        return None
    consent = _read_consent() or {}
    return {
        'privacyNoticeVersion': consent.get('notice_version'),
        'consentedAt': consent.get('decided_at'),
    }


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


def _empty_state():
    return {
        'schema_version': SCHEMA_VERSION,
        'anonymous_id': None,
        'workflows': [],
        'invocations': [],
        'session_workflows': {},
        'upload': {
            'retry_count': 0,
            'last_attempt': None,
            'last_ack_at': None,
        },
    }


def _normalize_state(value):
    state = _empty_state()
    if isinstance(value, dict):
        for key in ('anonymous_id', 'workflows', 'invocations',
                    'session_workflows'):
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
        item.pop('xfyun_user_id', None)
    for item in state['invocations']:
        item.pop('hit_count', None)
    if not isinstance(state.get('session_workflows'), dict):
        state['session_workflows'] = {}
    return state


def load_state():
    if not STATE_PATH.exists():
        return _empty_state()
    try:
        return _normalize_state(json.loads(STATE_PATH.read_text(encoding='utf-8')))
    except Exception:
        try:
            suffix = datetime.now().strftime('%Y%m%d%H%M%S')
            STATE_PATH.replace(STATE_PATH.with_name('state.corrupt-' + suffix + '.json'))
        except Exception:
            pass
        return _empty_state()


def save_state(state):
    value = _normalize_state(state)
    value['updated_at'] = now_iso()
    atomic_write_json(STATE_PATH, value)
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
    return {key: _sanitize_detail_value(value)
            for key, value in detail.items()
            if key not in ('source', 'path', 'cwd', 'file_path')}


def plugin_root():
    value = os.environ.get('CLAUDE_PLUGIN_ROOT')
    return Path(value) if value else Path(__file__).resolve().parent.parent


def plugin_version():
    try:
        meta = json.loads((plugin_root() / '.claude-plugin' / 'plugin.json')
                          .read_text(encoding='utf-8'))
        return meta.get('version', 'unknown')
    except Exception:
        return 'unknown'


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


def spawn_uploader(force=False):
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
    except Exception:
        pass
