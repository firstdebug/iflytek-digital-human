import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import telemetry_common as tc
import uploader
import xfyun_common


class AccountIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.telemetry_dir = self.root / 'telemetry'
        self.cookie_file = self.root / 'xfyun_cookies.json'
        self.patches = [
            mock.patch.multiple(
                tc,
                TELEMETRY_DIR=self.telemetry_dir,
                STATE_PATH=self.telemetry_dir / 'state.json',
                STATE_BACKUP_PATH=self.telemetry_dir / 'state.backup.json',
                STATE_LOCK_PATH=self.telemetry_dir / 'state.lock',
                CONSENT_PATH=self.telemetry_dir / 'consent.json',
                CURRENT_SESSION_PATH=self.telemetry_dir / 'current_session',
            ),
            mock.patch.object(tc, 'resolve_cookie_file', return_value=self.cookie_file),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

    def consent(self):
        notice = {'notice_version': '2.2', 'upload_endpoint': 'http://telemetry'}
        return mock.patch.object(tc, 'load_privacy_notice', return_value=notice), mock.patch.object(
            tc, '_read_consent', return_value={
                'accepted': True,
                'notice_version': '2.2',
                'notice_digest': tc._notice_digest(notice),
            })

    def test_consent_without_cookie_cannot_upload(self):
        with self.consent()[0], self.consent()[1]:
            self.assertFalse(tc.can_upload('http://telemetry'))

    def test_complete_cookie_stamps_and_payload_only_uses_xfyun_id(self):
        with self.consent()[0], self.consent()[1]:
            state = tc._empty_state()
            state['workflows'] = [{
                'workflow_id': 'wf-1',
                'workflow_type': 'live_streaming',
                'upload_status': 'pending',
                'xfyun_user_id': 'account-1',
            }]
            state['invocations'] = [{
                'invocation_id': 'inv-1',
                'workflow_id': 'wf-1',
                'skill_name': 'avatar-live-streaming',
                'upload_status': 'pending',
                'xfyun_user_id': 'account-1',
            }]
            tc.save_state(state)
            self.cookie_file.write_text(json.dumps({
                'account_id': 'account-1', 'ssoSessionId': 'session-secret'
            }), encoding='utf-8')
            workflows, invocations = uploader.pending_snapshot(50)
            payload = uploader._payload({}, workflows, invocations)
            self.assertEqual(payload['xfyunUserId'], 'account-1')
            self.assertNotIn('anonymousId', payload)
            self.assertEqual(workflows[0]['xfyunUserId'], 'account-1')

    def test_null_workflow_type_is_not_uploaded(self):
        with self.consent()[0], self.consent()[1]:
            state = tc._empty_state()
            state['workflows'] = [{
                'workflow_id': 'wf-null',
                'workflow_type': None,
                'upload_status': 'pending',
                'xfyun_user_id': 'account-1',
            }, {
                'workflow_id': 'wf-ok',
                'workflow_type': 'live_streaming',
                'upload_status': 'pending',
                'xfyun_user_id': 'account-1',
            }]
            state['invocations'] = [{
                'invocation_id': 'inv-null',
                'workflow_id': 'wf-null',
                'skill_name': 'avatar-workflow-entry',
                'upload_status': 'pending',
                'xfyun_user_id': 'account-1',
            }, {
                'invocation_id': 'inv-ok',
                'workflow_id': 'wf-ok',
                'skill_name': 'avatar-live-streaming',
                'upload_status': 'pending',
                'xfyun_user_id': 'account-1',
            }]
            tc.save_state(state)
            self.cookie_file.write_text(json.dumps({
                'account_id': 'account-1', 'ssoSessionId': 'session-secret'
            }), encoding='utf-8')
            workflows, invocations = uploader.pending_snapshot(50)
            self.assertEqual([item['workflowId'] for item in workflows], ['wf-ok'])
            self.assertEqual([item['invocationId'] for item in invocations], ['inv-ok'])

    def test_partial_cookie_still_waits(self):
        self.cookie_file.write_text(json.dumps({'account_id': 'account-1'}), encoding='utf-8')
        self.assertIsNone(tc.load_xfyun_login())
        self.cookie_file.write_text(json.dumps({'ssoSessionId': 'secret'}), encoding='utf-8')
        self.assertIsNone(tc.load_xfyun_login())

    def test_uploader_sends_auth_only_as_non_redirected_cookie_header(self):
        self.cookie_file.write_text(json.dumps({
            'account_id': 'account-1', 'ssoSessionId': 'session-secret'
        }), encoding='utf-8')

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def read():
                return b'{"data":{}}'

        payload = {'xfyunUserId': 'account-1', 'workflows': [], 'invocations': []}
        with mock.patch.object(uploader.urllib.request, 'urlopen',
                               return_value=Response()) as urlopen:
            uploader.post({'endpoint': 'http://telemetry', 'timeout_ms': 100}, payload)

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.get_header('Cookie'),
            'account_id=account-1; ssoSessionId=session-secret')
        self.assertNotIn('Cookie', request.headers)
        self.assertNotIn('ssoSessionId', request.data.decode('utf-8'))

    def test_save_cookies_triggers_flush_without_propagating_errors(self):
        with mock.patch.object(xfyun_common, '_active_cookie_file', return_value=self.cookie_file), \
                mock.patch.object(xfyun_common, '_flush_telemetry') as flush:
            xfyun_common.save_cookies({'account_id': 'a', 'ssoSessionId': 's'})
        flush.assert_called_once_with()

    def test_save_cookies_replaces_configured_target(self):
        default_file = self.root / 'default-cookies.json'
        with mock.patch.object(xfyun_common, 'COOKIE_FILE', default_file), \
                mock.patch.dict('os.environ', {'XFYUN_AVATAR_COOKIE_FILE': str(self.cookie_file)}), \
                mock.patch.object(xfyun_common, '_flush_telemetry'):
            xfyun_common.save_cookies({'account_id': 'a', 'ssoSessionId': 's'})
        self.assertFalse(default_file.exists())
        self.assertEqual(json.loads(self.cookie_file.read_text(encoding='utf-8'))['account_id'], 'a')

    def test_get_session_with_existing_cookie_does_not_flush_or_login(self):
        session = object()
        with mock.patch.object(xfyun_common, 'load_cookies', return_value={
                'account_id': 'a', 'ssoSessionId': 's'}), \
                mock.patch.object(xfyun_common, 'build_session', return_value=session), \
                mock.patch.object(xfyun_common, '_flush_telemetry') as flush, \
                mock.patch.object(xfyun_common, '_do_browser_login') as login:
            self.assertIs(session, xfyun_common.get_session())
        flush.assert_not_called()
        login.assert_not_called()

    def test_successful_json_requests_flush(self):
        class Response:
            status_code = 200
            text = ''

            @staticmethod
            def json():
                return {'code': 0, 'flag': True}

        class Session:
            def post(self, *args, **kwargs):
                return Response()

            def get(self, *args, **kwargs):
                return Response()

            def put(self, *args, **kwargs):
                return Response()

            def delete(self, *args, **kwargs):
                return Response()

        session = Session()
        calls = (
            lambda: xfyun_common.post(session, 'https://example.test', {}),
            lambda: xfyun_common.get(session, 'https://example.test'),
            lambda: xfyun_common.put(session, 'https://example.test', {}),
            lambda: xfyun_common.delete(session, 'https://example.test'),
        )
        tc.write_current_session('claude-session')
        with mock.patch.object(xfyun_common, '_flush_telemetry') as flush:
            for call in calls:
                self.assertEqual(call()['code'], 0)
        self.assertEqual(flush.call_count, len(calls))
        stats = tc.load_state()['session_request_stats']['claude-session']
        self.assertEqual(stats['platform_ok'], len(calls))
        self.assertEqual(stats['telemetry_post'], 0)
        self.assertEqual(stats['telemetry_post_fail'], 0)

    def test_80000_invalidates_cookie_without_login_flush_or_upload(self):
        class Response:
            status_code = 200
            text = ''

            @staticmethod
            def json():
                return {'code': 80000, 'flag': False}

        class Session:
            @staticmethod
            def post(*args, **kwargs):
                return Response()

        self.cookie_file.write_text(json.dumps({
            'account_id': 'account-1', 'ssoSessionId': 'expired-session'
        }), encoding='utf-8')
        state = tc._empty_state()
        state['workflows'] = [{
            'workflow_id': 'wf-1', 'xfyun_user_id': 'account-1',
            'upload_status': 'pending',
        }]
        tc.save_state(state)
        tc.write_current_session('claude-session')

        with mock.patch.object(
                xfyun_common, '_active_cookie_file', return_value=self.cookie_file), \
                mock.patch.object(xfyun_common, '_flush_telemetry') as flush, \
                mock.patch.object(xfyun_common, '_do_browser_login') as login:
            self.assertIsNone(xfyun_common.post(
                Session(), 'https://example.test', {}))

        self.assertFalse(self.cookie_file.exists())
        self.assertIsNone(tc.load_xfyun_login())
        flush.assert_not_called()
        login.assert_not_called()
        self.assertNotIn('claude-session', tc.load_state()['session_request_stats'])

        post = mock.Mock()
        with self.consent()[0], self.consent()[1]:
            self.assertFalse(tc.can_upload('http://telemetry'))
            result = uploader.upload_all(
                {'endpoint': 'http://telemetry', 'batch_size': 50},
                {'retry_count': 0, 'last_attempt': None},
                post_fn=post,
            )
        self.assertEqual(result, (0, 0))
        post.assert_not_called()
        self.assertEqual(
            tc.load_state()['workflows'][0]['upload_status'], 'pending')

    def test_uploader_http_response_and_network_failure_are_counted_locally(self):
        tc.write_current_session('claude-session')

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def read():
                return b'{"data":{"acceptedWorkflowIds":[],"acceptedInvocationIds":[]}}'

        with mock.patch.object(uploader, 'load_xfyun_auth', return_value={
                'account_id': 'account-1', 'ssoSessionId': 'session-secret'}):
            with mock.patch.object(uploader.urllib.request, 'urlopen', return_value=Response()):
                uploader.post({'endpoint': 'http://telemetry', 'timeout_ms': 100}, {})
            with mock.patch.object(uploader.urllib.request, 'urlopen',
                                   side_effect=OSError('offline')):
                with self.assertRaises(OSError):
                    uploader.post({'endpoint': 'http://telemetry', 'timeout_ms': 100}, {})

        stats = tc.load_state()['session_request_stats']['claude-session']
        self.assertEqual(stats['telemetry_post'], 1)
        self.assertEqual(stats['telemetry_post_fail'], 1)

    def test_decline_clears_session_request_stats(self):
        tc.write_current_session('claude-session')
        tc.increment_session_request('platform_ok')
        notice = {'notice_version': '2.2', 'upload_endpoint': 'http://telemetry'}
        with mock.patch.object(tc, 'load_privacy_notice', return_value=notice):
            tc.set_consent(False)

        self.assertFalse(tc.STATE_PATH.exists())
        self.assertEqual(tc.load_state()['session_request_stats'], {})


if __name__ == '__main__':
    unittest.main()
