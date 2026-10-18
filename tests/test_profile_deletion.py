"""Deletion preserves active runs, unrelated files and window reservations."""
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch
from tests import test_run_profiles
from tracker.run_profiles import RunProfileStore, acquire_run_lock
from desktop import automatic_session
import desktop

class ProfileDeletionStoreTests(unittest.TestCase):
    def test_deletes_only_named_run_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RunProfileStore(Path(folder) / 'runtime')
            first = store.create('Borrar')
            second = store.create('Conservar')
            (store.require(first['id']) / 'state.json').write_text('private run')
            keep = store.require(second['id']) / 'state.json'
            keep.write_text('keep')
            store.delete(first['id'])
            self.assertFalse(store.directory(first['id']).exists())
            self.assertEqual(keep.read_text(), 'keep')
            self.assertNotIn(first, RunProfileStore(store.runtime).profiles())
            for unsafe in ('principal', '../outside', 'unknown', None):
                with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                    store.delete(unsafe)

    def test_locked_run_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RunProfileStore(Path(folder) / 'runtime')
            created = store.create('Ocupada')
            with acquire_run_lock(folder, created['id']):
                with self.assertRaises(RuntimeError):
                    store.delete(created['id'])
            self.assertTrue(store.require(created['id']).exists())
            store.delete(created['id'])
            self.assertFalse(store.directory(created['id']).exists())

    def test_deleted_secondary_is_not_recreated_by_automatic_window(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RunProfileStore(Path(folder) / 'runtime')
            store.delete('segundo-jugador')
            self.assertNotIn('segundo-jugador', [p['id'] for p in store.profiles()])
            created = store.create('Otra')
            with acquire_run_lock(folder, 'principal'):
                profile, lock, slot, slot_lock = automatic_session(folder)
                try:
                    self.assertEqual(profile, created['id'])
                    self.assertFalse(store.directory('segundo-jugador').exists())
                finally:
                    lock.close()
                    slot_lock.close()

    def test_automatic_window_rechecks_candidate_after_lock_acquisition(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RunProfileStore(Path(folder) / 'runtime')
            created = store.create('Reserva')
            original = desktop.acquire_profile_lock
            removed = False
            def acquire(home, ident):
                nonlocal removed
                if ident == 'segundo-jugador' and not removed:
                    removed = True
                    store.delete(ident)
                return original(home, ident)
            with acquire_run_lock(folder, 'principal'), patch('desktop.acquire_profile_lock', side_effect=acquire):
                profile, lock, slot, slot_lock = automatic_session(folder)
                try:
                    self.assertTrue(removed)
                    self.assertEqual(profile, created['id'])
                    self.assertFalse(store.directory('segundo-jugador').exists())
                finally:
                    lock.close()
                    slot_lock.close()

    def test_rejects_link_before_any_deletion(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RunProfileStore(Path(folder) / 'runtime')
            created = store.create('Enlace')
            target = store.require(created['id'])
            outside = Path(folder) / 'outside'
            outside.mkdir()
            keep = outside / 'save.bin'
            keep.write_bytes(b'keep')
            link = target / 'linked'
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest('Windows does not permit test symlinks')
            try:
                with self.assertRaises(ValueError):
                    store.delete(created['id'])
                self.assertEqual(keep.read_bytes(), b'keep')
                self.assertTrue((target / 'run-profile.json').exists())
            finally:
                link.unlink()

class ProfileDeletionHTTPTests(unittest.TestCase):
    setUp = test_run_profiles.LiveRunProfilesTests.setUp
    tearDown = test_run_profiles.LiveRunProfilesTests.tearDown
    post = test_run_profiles.LiveRunProfilesTests.post

    def test_switch_rechecks_existence_after_acquiring_target_lock(self):
        ident = self.backend.create_profile('Se elimina en otra ventana')['created']
        current = self.backend.service
        original = desktop.acquire_profile_lock
        def acquire(home, target):
            if target == ident:
                self.backend.profiles.delete(target)
            return original(home, target)
        with patch('desktop.acquire_profile_lock', side_effect=acquire):
            with self.assertRaises(ValueError):
                self.backend.switch_profile(ident)
        self.assertEqual(self.backend.profile, 'principal')
        self.assertIs(self.backend.service, current)
        self.assertFalse(current.stop.is_set())
        self.assertFalse(self.backend.profiles.directory(ident).exists())
        with acquire_run_lock(self.root, ident):
            pass
    def test_delete_http_preserves_active_and_reserved_profiles(self):
        created = self.post({'action': 'create', 'name': 'Borrable'})['created']
        service = self.backend.service
        with acquire_run_lock(self.root, created):
            with self.assertRaises(HTTPError) as error:
                self.post({'action': 'delete', 'id': created})
            self.assertEqual(error.exception.code, 400)
        for ident in ('principal',):
            with self.assertRaises(HTTPError):
                self.post({'action': 'delete', 'id': ident})
        self.backend.switch_profile(created)
        with self.assertRaises(HTTPError):
            self.post({'action': 'delete', 'id': created})
        self.backend.switch_profile('principal')
        result = self.post({'action': 'delete', 'id': created})
        self.assertEqual(result['active'], 'principal')
        self.assertNotIn(created, [p['id'] for p in result['profiles']])
        self.assertFalse(self.backend.profiles.directory(created).exists())
        self.assertFalse(self.backend.service.stop.is_set())

if __name__ == '__main__':
    unittest.main()
