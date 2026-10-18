"""Authenticated API wiring for runs, direct Soul Link and OBS counters."""
import base64
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from server import make_handler, runtime_directory
from tracker.layout_export import blank_sprite
from tracker.overlay import OverlayManager
from tracker.service import TrackerService


class FeatureApiTests(unittest.TestCase):
    def test_explicit_principal_uses_original_runtime_and_lock_home(self):
        root = Path('example-home')
        self.assertEqual(runtime_directory(root, 'principal'), runtime_directory(root))
        from desktop import LocalBackend
        implicit = LocalBackend(runtime_directory(root), 'principal')
        explicit = LocalBackend(runtime_directory(root, 'principal'), 'principal')
        self.assertEqual(implicit.profiles.runtime, explicit.profiles.runtime)
        self.assertEqual(implicit.lock_home, explicit.lock_home)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.service = TrackerService(root / 'state.json')
        self.overlay = OverlayManager(self.service, root, root / 'layout')
        self.profiles = SimpleNamespace(
            request_lock=threading.RLock(),
            profiles_status=Mock(return_value={'active': 'principal', 'profiles': []}),
            create_profile=Mock(return_value={'created': 'new'}),
            switch_profile=Mock(return_value={'active': 'new'}),
            delete_profile=Mock(return_value={'active': 'principal', 'profiles': []}))
        self.companion = SimpleNamespace(perform=Mock(return_value={'configured': True}))
        self.servers = []
        self.port = self.start_server()
        self.addCleanup(self.close_servers)

    def start_server(self, remote=False):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(
            self.service, 'test-token', self.companion, overlay=self.overlay,
            profiles=self.profiles, remote_only=remote))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.servers.append((server, worker))
        return server.server_port

    def close_servers(self):
        for server, worker in self.servers:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)

    def request(self, method, path, payload=None, authorized=True, port=None):
        conn = http.client.HTTPConnection('127.0.0.1', port or self.port, timeout=5)
        headers = {'X-Tracker-Token': 'test-token'} if authorized else {}
        conn.request(method, path, json.dumps(payload) if payload is not None else None, headers)
        result = conn.getresponse()
        status, body, response_headers = result.status, result.read(), dict(result.getheaders())
        conn.close()
        return status, body, response_headers

    def test_named_run_api_requires_token_and_routes_actions(self):
        self.assertEqual(self.request('GET', '/api/profiles')[0], 200)
        self.assertEqual(self.request('POST', '/api/profiles', {'action': 'create', 'name': 'Luna'}, False)[0], 403)
        self.profiles.create_profile.assert_not_called()
        self.assertEqual(self.request('POST', '/api/profiles', {'action': 'create', 'name': 'Luna'})[0], 200)
        self.profiles.create_profile.assert_called_once_with('Luna')
        self.assertEqual(self.request('POST', '/api/profiles', {'action': 'select', 'id': 'new'})[0], 200)
        self.profiles.switch_profile.assert_called_once_with('new')
        self.assertEqual(self.request('POST', '/api/profiles', {'action': 'delete'})[0], 400)
        self.profiles.delete_profile.assert_not_called()
        self.assertEqual(self.request('POST', '/api/profiles', {'action': 'delete', 'id': 'new'}, False)[0], 403)
        self.profiles.delete_profile.assert_not_called()
        self.assertEqual(self.request('POST', '/api/profiles', {'action': 'delete', 'id': 'new'})[0], 200)
        self.profiles.delete_profile.assert_called_once_with('new')

    def test_old_profile_handlers_reject_all_mutations(self):
        self.service.stop.set()
        self.assertEqual(self.request('POST', '/api/profiles', {'action': 'select', 'id': 'new'})[0], 409)
        self.assertEqual(self.request('POST', '/api/command', {'action': 'scan'})[0], 409)
        self.profiles.switch_profile.assert_not_called()
        self.assertTrue(self.service.commands.empty())

    def test_direct_soullink_actions_require_local_authentication(self):
        for action in ('direct_host', 'direct_join'):
            payload = {'action': action, 'host': '127.0.0.1', 'name': 'Luna'}
            self.assertEqual(self.request('POST', '/api/companion', payload, False)[0], 403)
            self.assertEqual(self.request('POST', '/api/companion', payload)[0], 200)
            self.companion.perform.assert_called_with(action, payload)

    def test_counter_icon_http_round_trip_and_invalid_upload(self):
        path = '/api/overlay/counter-icon'
        payload = {'data': base64.b64encode(blank_sprite(32)).decode()}
        self.assertEqual(self.request('GET', '/overlay/counter-icon.png')[0], 404)
        self.assertEqual(self.request('POST', path, payload, False)[0], 403)
        self.assertEqual(self.request('POST', path, payload)[0], 200)
        status, image, headers = self.request('GET', '/overlay/counter-icon.png')
        self.assertEqual(status, 200)
        self.assertTrue(image.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(headers['Content-Type'], 'image/png')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        config = json.loads(self.request('GET', '/api/overlay/settings')[1])
        self.assertNotEqual(config['counter_icon_version'], '0')
        self.assertEqual(self.request('POST', path, {'data': 'invalid'})[0], 400)
        self.assertEqual(self.request('GET', '/overlay/counter-icon.png')[1], image)

    def test_remote_overlay_serves_icon_but_cannot_manage_runs_or_soullink(self):
        self.overlay.import_counter_icon(base64.b64encode(blank_sprite(32)).decode())
        port = self.start_server(remote=True)
        self.assertEqual(self.request('GET', '/overlay/counter-icon.png', port=port)[0], 200)
        for path in ('/api/profiles', '/api/session', '/api/companion'):
            self.assertEqual(self.request('GET', path, port=port)[0], 404)
            self.assertEqual(self.request('POST', path, {}, port=port)[0], 403)
