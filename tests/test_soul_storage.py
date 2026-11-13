"""Identity/cache migration and individual recovery credentials are separate from full views."""
import os
import tempfile
import unittest
from pathlib import Path

from companion.room import Room
from companion.room_storage import RoomStorage
from companion.snapshot import snapshot
from companion.soul_room import SoulRoom
from companion.soul_storage import SoulStorage
from tests.test_companion import state


class SoulStorageTests(unittest.TestCase):
    def test_reuses_existing_identity_without_copying_full_legacy_views(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = RoomStorage(root)
            identity = legacy.identity('Anterior', 'Ultra Sun 1.0')
            room = Room(identity, 4)
            value = snapshot(state())
            value['party'][0]['nickname'] = 'LEGACY_FULL_PRIVATE_MARKER'
            room.exchange(identity['player_id'], {'protocol': 2, 'session_id': room.session_id,
                'epoch': room.epoch, 'run_id': identity['run_id'], 'sequence': 1, 'state': value})
            legacy.cache(room.view())
            before = legacy.path.read_bytes()
            storage = SoulStorage(root)
            self.assertEqual(storage.identity('Anterior', 'Ultra Sun 1.0'), identity)
            self.assertIsNone(storage.data['room'])
            storage.cache(SoulRoom(identity).view())
            self.assertNotIn('LEGACY_FULL_PRIVATE_MARKER', storage.path.read_text(encoding='utf-8'))
            self.assertEqual(legacy.path.read_bytes(), before,
                             'Loading the new cache does not edit a legacy connection implicitly')

    def test_shared_full_view_is_never_persisted_and_restart_is_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = SoulStorage(Path(directory))
            identity = storage.identity('Local', 'Ultra Sun 1.0')
            room = SoulRoom(identity)
            value = snapshot(state())
            value['party'][0]['nickname'] = 'FULL_CACHE_LEAK_MARKER'
            room.exchange(identity['player_id'], {'protocol': 3, 'session_id': room.session_id,
                'epoch': room.epoch, 'run_id': identity['run_id'], 'sequence': 1,
                'sharing': True, 'source_live': True, 'state': value, 'links': {},
                'soul': {'captures': {}, 'missed_routes': []}})
            storage.cache(room.view())
            self.assertNotIn('FULL_CACHE_LEAK_MARKER', storage.path.read_text(encoding='utf-8'))
            restored = SoulStorage(Path(directory))
            self.assertEqual(restored.data['player_id'], identity['player_id'])
            self.assertIsNone(restored.data['room']['members'][0]['state'])
            self.assertFalse(restored.data['room']['members'][0]['online'])
            self.assertEqual(restored.data['room']['members'][0]['view_ttl_ms'], 0)

    def test_individual_secret_is_protected_separate_and_retirement_keeps_run_data(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = SoulStorage(Path(directory))
            identity = storage.identity('Local', 'Ultra Sun 1.0')
            room = SoulRoom(identity)
            token = 'x' * 43
            storage.save_credentials('http://127.0.0.1:8770', token, identity, room.view())
            recovered = storage.credentials()
            self.assertEqual(recovered['token'], token)
            self.assertEqual(recovered['player_id'], identity['player_id'])
            self.assertEqual(recovered['run_id'], identity['run_id'])
            self.assertEqual(set(recovered), {'base', 'token', 'session_id', 'epoch', 'player_id', 'run_id', 'game'})
            self.assertNotIn(token, storage.path.read_text(encoding='utf-8'))
            if os.name == 'nt':
                self.assertTrue(storage.credentials_path.read_bytes().startswith(b'SL3D'))
                self.assertNotIn(token.encode(), storage.credentials_path.read_bytes())
            else:
                self.assertEqual(storage.credentials_path.stat().st_mode & 0o077, 0)
            storage.retire_membership()
            fresh = storage.identity('Local', identity['game'])
            self.assertNotEqual(fresh['player_id'], identity['player_id'])
            self.assertEqual(fresh['run_id'], identity['run_id'])
            self.assertFalse(storage.credentials_path.exists())

    def test_corrupt_future_metadata_and_invalid_credentials_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'companion-soul.json'
            for content in ('{', '{"version":2}', '{"version":true}'):
                path.write_text(content, encoding='utf-8')
                storage = SoulStorage(root)
                self.assertTrue(storage.error)
                with self.assertRaises(ValueError):
                    storage.identity('Local', 'Ultra Sun 1.0')
                self.assertEqual(path.read_text(encoding='utf-8'), content)
            path.unlink()
            storage = SoulStorage(root)
            storage.credentials_path.write_bytes(b'not-valid-credentials')
            self.assertIsNone(storage.credentials())
            self.assertTrue(storage.credential_error)
            self.assertEqual(storage.credentials_path.read_bytes(), b'not-valid-credentials')


if __name__ == '__main__':
    unittest.main()
