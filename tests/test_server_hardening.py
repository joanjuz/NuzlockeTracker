"""Servidor local: respuestas seguras ante archivos ausentes, origen cruzado y conexiones colgadas."""
import http.client
import json
import socket
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from desktop import LocalBackend
from server import make_handler
from tracker.layout_export import BLANK_PNG, PartyLayoutExporter
from tracker.overlay import OverlayManager
from tracker.service import TrackerService


class ServerHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.service = TrackerService(root / 'runtime' / 'state.json')
        (root / 'layout').mkdir()
        self.overlay = OverlayManager(self.service, root / 'runtime', root / 'layout')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(
            self.service, 'tok', overlay=self.overlay, sprite_cache=root / 'cache'))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.service.stop.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def get(self, path, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        conn.request('GET', path, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_missing_webp_is_404_not_a_dropped_connection(self):
        status, _ = self.get('/overlay/media/pokemon_1.webp')
        self.assertEqual(status, 404)
        self.assertEqual(self.get('/overlay/media/pokemon_1.png')[0], 200)

    def test_routes_can_be_requested_for_partner_game(self):
        self.service.update(game='Pokémon X 1.0')
        own = json.loads(self.get('/api/routes')[1])
        self.assertEqual(own['game'], 'Pokémon X 1.0')
        partner = json.loads(self.get('/api/routes?game=Ultra%20Moon%201.0')[1])
        self.assertEqual(partner['game'], 'Ultra Moon 1.0')
        self.assertTrue(partner['routes'])
        unknown = json.loads(self.get('/api/routes?game=Inventado')[1])
        self.assertEqual(unknown['routes'], [])

    def test_cross_site_pages_cannot_trigger_sprite_downloads(self):
        with patch('server.fetch_sprite', return_value=BLANK_PNG) as fetch:
            status, _ = self.get('/soullink/sprite/25.png', {'Sec-Fetch-Site': 'cross-site'})
            self.assertEqual(status, 403)
            fetch.assert_not_called()
            self.assertEqual(self.get('/soullink/sprite/25.png', {'Sec-Fetch-Site': 'same-origin'})[0], 200)

    def headers_of(self, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        conn.request('GET', path)
        response = conn.getresponse()
        response.read()
        conn.close()
        return response.status, dict(response.getheaders())

    def test_html_pages_carry_a_strict_script_policy(self):
        for path in ('/', '/overlay', '/overlay/editor'):
            with self.subTest(path=path):
                status, headers = self.headers_of(path)
                self.assertEqual(status, 200)
                policy = headers.get('Content-Security-Policy', '')
                self.assertIn("script-src 'self'", policy)
                self.assertNotIn("'unsafe-inline'", policy.split('script-src', 1)[1].split(';', 1)[0])
                self.assertIn("object-src 'none'", policy)
                self.assertIn('ws://127.0.0.1:%d' % self.server.server_port, policy)
        status, headers = self.headers_of('/theme.js')
        self.assertEqual(status, 200)
        self.assertNotIn('Content-Security-Policy', headers)

    def test_no_inline_scripts_or_handlers_in_pages(self):
        import re
        root = Path(__file__).resolve().parent.parent / 'web'
        for page in root.glob('*.html'):
            with self.subTest(page=page.name):
                html = page.read_text(encoding='utf-8')
                self.assertIsNone(re.search(r'<script(?![^>]*\bsrc=)[^>]*>', html))
                self.assertIsNone(re.search(r'\son[a-z]+\s*=', html))

    def test_idle_connection_is_closed_by_timeout(self):
        handler = self.server.RequestHandlerClass
        self.assertIsNotNone(handler.timeout)
        self.assertLessEqual(handler.timeout, 30)
        handler.timeout = 0.3
        try:
            sock = socket.create_connection(('127.0.0.1', self.server.server_port), timeout=5)
            start = time.monotonic()
            # Send nothing: the server must hang up instead of waiting forever.
            self.assertEqual(sock.recv(1024), b'')
            self.assertLess(time.monotonic() - start, 4)
            sock.close()
        finally:
            handler.timeout = 10


class VersionTests(unittest.TestCase):
    def test_visible_version_matches_latest_release_notes(self):
        import re
        from tracker import __version__
        notes = Path(__file__).resolve().parent.parent / 'docs' / 'releases'
        versions = [tuple(map(int, m.groups())) for f in notes.glob('v*.md')
                    if (m := re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)\.md', f.name))]
        self.assertEqual(__version__, '.'.join(map(str, max(versions))))
        self.assertNotRegex((notes.parent.parent / 'web' / 'index.html').read_text(encoding='utf-8'),
                            r'Progressive \d+\.\d+')


class DemoIsolationTests(unittest.TestCase):
    def test_demo_never_reads_real_soullink_credentials(self):
        from companion.sync import CompanionSync
        from server import companion_directory
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / 'runtime'
            runtime.mkdir()
            (runtime / 'companion-credentials.json').write_text(json.dumps({
                'worker_url': 'https://example.workers.dev', 'token': 'a' * 48,
                'pair_id': 'p', 'name': 'Yo', 'game': 'Ultra Moon 1.0'}), encoding='utf-8')
            self.assertEqual(companion_directory(runtime), runtime)
            demo = CompanionSync(TrackerService(runtime / 'demo-state.json'), companion_directory(runtime, demo=True))
            self.assertEqual(demo.settings, {})
            self.assertNotIn('a' * 48, json.dumps(demo.status()))


class ShareSurvivesProfileSwitchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [
            patch('desktop.PartyLayoutExporter', side_effect=lambda *a, **k:
                  PartyLayoutExporter(*a, downloader=lambda _: BLANK_PNG, **k)),
            patch('desktop.CompanionSync.start'),
        ]
        for mock in self.patches:
            mock.start()
        self.backend = LocalBackend(self.root / 'runtime', 'principal').start()

    def tearDown(self):
        self.backend.close()
        for mock in reversed(self.patches):
            mock.stop()
        self.temp.cleanup()

    def test_vpn_share_is_restored_after_switch(self):
        ident = self.backend.create_profile('Otra partida')['created']
        with patch('server.RemoteOverlayShare.status',
                   return_value={'enabled': True, 'ip': '26.1.2.3', 'port': 9123}), \
                patch('server.RemoteOverlayShare.configure') as configure:
            self.backend.switch_profile(ident)
        configure.assert_called_once_with(True, '26.1.2.3')
        # Same port first, so OBS sources over the VPN keep their URL.
        self.assertEqual(self.backend.remote_share.preferred_port, 9123)


if __name__ == '__main__':
    unittest.main()
