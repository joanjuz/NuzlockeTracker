import json
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch
from server import TrackerHTTPServer, make_handler

class ProcessListingTests(unittest.TestCase):
    def serve(self, remote=False):
        self.server = TrackerHTTPServer(('127.0.0.1', 0), make_handler(object(), 'test', remote_only=remote))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, headers=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request('GET', '/api/processes', headers=headers or {})
            result = conn.getresponse()
            return result.status, json.loads(result.read())
        finally:
            conn.close()

    def test_listing_preserves_title_game_and_process_identity(self):
        self.serve()
        with patch('server.list_emulator_instances', return_value=[{
            'pid': 42, 'name': 'lime3ds.exe', 'title': 'Pokémon Ultra Moon',
            'game_hint': 'Ultra Moon 1.0', 'creation_id': 123456}]) as listing:
            code, data = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(data, {'processes': [{'pid': 42, 'name': 'lime3ds.exe',
            'title': 'Pokémon Ultra Moon', 'game': 'Ultra Moon 1.0', 'creation_time': 123456}]})
        listing.assert_called_once_with()

    def test_enumeration_failure_is_visible_and_manual_pid_remains_possible(self):
        self.serve()
        with patch('server.list_emulator_instances', side_effect=OSError('Acceso denegado')):
            code, data = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(data, {'processes': [], 'error': 'Acceso denegado'})

    def test_vpn_source_cannot_enumerate_private_processes(self):
        self.serve(remote=True)
        with patch('server.list_emulator_instances') as listing:
            self.assertEqual(self.request()[0], 404)
        listing.assert_not_called()

    def test_foreign_origin_cannot_enumerate_private_processes(self):
        self.serve()
        with patch('server.list_emulator_instances') as listing:
            self.assertEqual(self.request({'Origin': 'https://elsewhere.example'})[0], 403)
        listing.assert_not_called()

if __name__ == '__main__':
    unittest.main()
