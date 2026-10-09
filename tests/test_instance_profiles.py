"""Local profile isolation: one PC can host both Soul Link players safely."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from companion.sync import CompanionSync
from server import make_handler, runtime_directory


class DummyService:
    def snapshot(self):
        return {'game':'Ultra Moon 1.0'}


class InstanceProfileTests(unittest.TestCase):
    def test_principal_keeps_original_runtime_directory(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(runtime_directory(root), Path(root) / 'runtime')

    def test_second_player_has_separate_state_progress_and_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            principal=runtime_directory(root)
            second=runtime_directory(root, 'segundo-jugador')
            self.assertNotEqual(principal, second)
            self.assertEqual(second, principal / 'profiles' / 'segundo-jugador')
            first_sync=CompanionSync(DummyService(), principal)
            second_sync=CompanionSync(DummyService(), second)
            self.assertNotEqual(first_sync.settings_path, second_sync.settings_path)
            self.assertNotEqual(first_sync.cache_path, second_sync.cache_path)
            first_sync._store(first_sync.settings_path, {'token': 'secret-first'})
            self.assertFalse(second_sync.settings_path.exists())
            self.assertEqual(json.loads(first_sync.settings_path.read_text())['token'], 'secret-first')

    def test_reject_unsafe_profiles(self):
        for profile in ('../runtime','/absolute','a/b','A','../','', '.','x' * 33):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                runtime_directory('/safe', profile)
        self.assertEqual(runtime_directory('/safe','ultra-moon'),
                         Path('/safe')/'runtime'/'profiles'/'ultra-moon')

    def test_session_distinguishes_tracker_instances(self):
        httpd=ThreadingHTTPServer(('127.0.0.1',0),make_handler(DummyService(), 'test-token', profile='segundo-jugador'))
        thread=threading.Thread(target=httpd.serve_forever,daemon=True)
        thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{httpd.server_port}/api/session') as response:
                payload=json.load(response)
            self.assertEqual(payload['profile'], 'segundo-jugador')
            self.assertEqual(payload['token'], 'test-token')
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()
