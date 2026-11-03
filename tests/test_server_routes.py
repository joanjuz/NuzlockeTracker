"""Tabla de rutas de tracker/api: mismas reglas que el antiguo make_handler."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from server import TrackerHTTPServer, make_handler
from tracker.api import ROUTES_GET, ROUTES_POST
from tracker.overlay import OverlayManager
from tracker.service import TrackerService
from tracker.updates import FALLBACK_URL, UpdateChecker
from tracker import __version__

# Lista blanca histórica de la VPN (server.py antes de tracker/api).
REMOTE_EXACT = {'/overlay', '/overlay.js', '/overlay.css', '/api/overlay/public',
                '/api/overlay/settings', '/fonts/Oxanium.ttf', '/overlay/counter-icon.png'}
REMOTE_PREFIXES = ('/overlay/media/pokemon_', '/overlay/item/', '/overlay/font/', '/overlay/hp-image/')
# Added on purpose after the split: OBS graveyard sprites (read-only, by stable id).
REMOTE_PATTERNS = {r'/overlay/graveyard/([0-9a-f]{12})'}


class RouteTableTests(unittest.TestCase):
    def test_remote_routes_match_the_historical_whitelist(self):
        remote = {r.pattern.pattern for r in ROUTES_GET if r.remote}
        self.assertEqual({p for p in remote if '(' in p and not p.endswith('(.*)')}, REMOTE_PATTERNS)
        remote -= REMOTE_PATTERNS
        literal = {p.replace('\\', '') for p in remote if not p.endswith('(.*)')}
        prefixes = {p.replace('\\', '').removesuffix('(.*)') for p in remote if p.endswith('(.*)')}
        self.assertEqual(literal, REMOTE_EXACT)
        self.assertEqual(prefixes, set(REMOTE_PREFIXES))
        self.assertFalse(any(r.remote for r in ROUTES_POST))

    def test_patterns_do_not_shadow_each_other(self):
        paths = [r.pattern.pattern for r in ROUTES_GET]
        self.assertEqual(len(paths), len(set(paths)))


class RouteBehaviourTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.service = TrackerService(root / 'runtime' / 'state.json')
        (root / 'layout').mkdir()
        self.overlay = OverlayManager(self.service, root / 'runtime', root / 'layout')
        self.checker = UpdateChecker(root / 'update-check.json', current='1.0.0', enabled=False)
        self.servers = []

    def tearDown(self):
        self.service.stop.set()
        for server, thread in self.servers:
            server.shutdown()
            server.server_close()
            thread.join()
        self.temp.cleanup()

    def serve(self, **options):
        server = TrackerHTTPServer(('127.0.0.1', 0), make_handler(self.service, 'tok', **options))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.servers.append((server, thread))
        return server.server_port

    def call(self, port, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request(method, path, body, headers or {})
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_malformed_overlay_media_on_vpn_is_plain_404(self):
        port = self.serve(overlay=self.overlay, remote_only=True)
        for path in ('/overlay/media/pokemon_9.png', '/overlay/item/abc', '/overlay/hp-image/x.png'):
            with self.subTest(path=path):
                self.assertEqual(self.call(port, 'GET', path), (404, b'{}'))
        status, raw = self.call(port, 'GET', '/overlay/media/other.png')
        self.assertEqual((status, json.loads(raw)), (404, {'error': 'Solo lectura OBS'}))

    def test_without_overlay_manager_overlay_routes_are_404(self):
        port = self.serve()
        self.assertEqual(self.call(port, 'GET', '/overlay'), (404, b'{}'))
        self.assertEqual(self.call(port, 'GET', '/api/overlay/settings'), (404, b'{}'))
        self.assertEqual(self.call(port, 'POST', '/api/overlay/settings', '{}',
                                   {'X-Tracker-Token': 'tok'}), (404, b'{}'))
        self.assertEqual(self.call(port, 'GET', '/app.js')[0], 200)

    def test_post_paths_keep_the_query_string_strict(self):
        port = self.serve(overlay=self.overlay)
        body = json.dumps({'action': 'scan'})
        self.assertEqual(self.call(port, 'POST', '/api/command?x=1', body, {'X-Tracker-Token': 'tok'})[0], 404)
        self.assertEqual(self.call(port, 'POST', '/api/command', body, {'X-Tracker-Token': 'tok'})[0], 202)

    def test_overlay_settings_size_limit(self):
        port = self.serve(overlay=self.overlay)
        status, raw = self.call(port, 'POST', '/api/overlay/settings', ' ' * 8193, {'X-Tracker-Token': 'tok'})
        self.assertEqual((status, json.loads(raw)['error']), (400, 'Solicitud de overlay demasiado grande'))

    def test_update_endpoint_is_local_only(self):
        port = self.serve(overlay=self.overlay, updates=self.checker)
        status, raw = self.call(port, 'GET', '/api/update')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), {'current': '1.0.0', 'latest': None, 'update_available': False,
                                           'url': FALLBACK_URL, 'checked_at': None})
        self.assertEqual(self.call(port, 'GET', '/api/update', headers={'Origin': 'https://evil.example'})[0], 403)
        remote = self.serve(overlay=self.overlay, updates=self.checker, remote_only=True)
        status, raw = self.call(remote, 'GET', '/api/update')
        self.assertEqual((status, json.loads(raw)), (404, {'error': 'Solo lectura OBS'}))

    def test_update_endpoint_without_checker_reports_current_version(self):
        port = self.serve()
        status, raw = self.call(port, 'GET', '/api/update')
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual((data['current'], data['latest'], data['update_available']), (__version__, None, False))


if __name__ == '__main__':
    unittest.main()
