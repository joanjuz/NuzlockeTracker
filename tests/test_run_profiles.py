"""Named runs preserve independent saves while keeping the live OBS address."""
import json
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from desktop import LocalBackend, LocalHTTPServer, automatic_session
from tracker.layout_export import PartyLayoutExporter, BLANK_PNG
from tracker.run_profiles import RunProfileStore, acquire_run_lock
from tracker.service import TrackerService


class RunProfileStoreTests(unittest.TestCase):
    def test_legacy_locations_remain_unchanged_and_new_run_is_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'runtime'
            root.mkdir()
            old = root / 'state.json'
            old.write_bytes(b'{"legacy":"preserved"}')
            secondary = root / 'profiles' / 'segundo-jugador'
            secondary.mkdir(parents=True)
            (secondary / 'companion-credentials.json').write_bytes(b'private-secondary')
            store = RunProfileStore(root)
            created = store.create('Ultra Luna · segunda partida')
            self.assertEqual(store.directory('principal'), root)
            self.assertEqual(store.directory('segundo-jugador'), secondary)
            self.assertEqual(old.read_bytes(), b'{"legacy":"preserved"}')
            self.assertEqual((secondary / 'companion-credentials.json').read_bytes(), b'private-secondary')
            self.assertEqual([p.name for p in store.directory(created['id']).iterdir()], ['run-profile.json'])
            reopened = RunProfileStore(root)
            self.assertIn(created, reopened.profiles())
            self.assertEqual(reopened.require(created['id']), store.directory(created['id']))

    def test_name_validation_and_generated_directory_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RunProfileStore(Path(folder) / 'runtime')
            for invalid in (None, '', '  ', 'a' * 65, 'bad\nname', 'bad\x00name'):
                with self.subTest(name=invalid), self.assertRaises(ValueError):
                    store.create(invalid)
            profile = store.create('  Una / partida : especial  ')
            self.assertEqual(profile['name'], 'Una / partida : especial')
            self.assertRegex(profile['id'], r'^run-[0-9a-f]{24}$')
            with self.assertRaises(ValueError):
                store.create('una / PARTIDA : especial')
            boundary = store.create('a' * 64)
            self.assertEqual(len(boundary['name']), 64)
            for invalid in ('../outside', '/outside', 'A', None, 'missing'):
                with self.subTest(profile=invalid), self.assertRaises(ValueError):
                    store.require(invalid)

    def test_existing_custom_profile_discovered_without_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            custom = root / 'profiles' / 'old-run'
            custom.mkdir(parents=True)
            (custom / 'run-profile.json').write_text('broken')
            self.assertIn({'id': 'old-run', 'name': 'old-run'}, RunProfileStore(root).profiles())

    def test_profile_lock_excludes_another_window_then_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            first = acquire_run_lock(folder, 'principal')
            try:
                with self.assertRaises(RuntimeError):
                    acquire_run_lock(folder, 'principal')
                second = acquire_run_lock(folder, 'segundo-jugador')
                second.close()
            finally:
                first.close()
            reopened = acquire_run_lock(folder, 'principal')
            reopened.close()


class LiveRunProfilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [
            patch('desktop.PartyLayoutExporter', side_effect=lambda *args, **kwargs:
                  PartyLayoutExporter(*args, downloader=lambda _: BLANK_PNG, **kwargs)),
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

    def post(self, payload):
        request = Request(self.backend.url + 'api/profiles',
                          data=json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json',
                                   'X-Tracker-Token': self.backend.token})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def test_http_switch_round_trip_isolates_team_boxes_progress_templates_obs_and_companion(self):
        service = self.backend.service
        mon = {'species_id': 25, 'nickname': 'Chispa', 'origin_version': 33,
               'encryption_constant': 1234, 'checksum_valid': True,
               'hp': 50, 'max_hp': 50}
        service.progress.mark_dead(mon)
        service.update(party=[mon] + [None] * 5, boxes={'1': [mon] + [None] * 29})
        service.templates.import_csv({'moves': 'Move,Power,PP\n15,70,10\n'})
        self.backend.overlay.set_settings({'gap': 29})
        (self.backend.runtime / 'companion-credentials.json').write_text(json.dumps({
            'worker_url': 'https://run-a.example.workers.dev', 'token': 'private-a', 'name': 'A'}))
        old_service = service
        old_worker = self.backend.worker
        url = self.backend.url
        created = self.post({'action': 'create', 'name': 'Otra aventura'})
        ident = created['created']
        switched = self.post({'action': 'select', 'id': ident})
        self.assertEqual(switched['active'], ident)
        self.assertEqual(self.backend.url, url)
        self.assertTrue(old_service.stop.is_set())
        self.assertFalse(old_worker.is_alive())
        self.assertEqual(self.backend.service.snapshot()['party'], [None] * 6)
        self.assertEqual(self.backend.service.snapshot()['boxes'], {})
        self.assertEqual(self.backend.service.progress.data['death_count'], 0)
        self.assertFalse(self.backend.service.templates.status()['loaded'])
        self.assertEqual(self.backend.overlay.get_settings()['gap'], 16)
        self.assertFalse(self.backend.companion.status()['configured'])
        self.backend.overlay.set_settings({'gap': 41})
        self.post({'action': 'select', 'id': 'principal'})
        self.assertEqual(self.backend.service.snapshot()['party'][0]['nickname'], 'Chispa')
        self.assertEqual(self.backend.service.snapshot()['boxes']['1'][0]['nickname'], 'Chispa')
        self.assertEqual(self.backend.service.progress.data['death_count'], 1)
        self.assertEqual(self.backend.service.templates.data['moves']['15']['power'], 70)
        self.assertEqual(self.backend.overlay.get_settings()['gap'], 29)
        self.assertEqual(self.backend.companion.settings['token'], 'private-a')
        self.post({'action': 'select', 'id': ident})
        self.assertEqual(self.backend.overlay.get_settings()['gap'], 41)
        self.assertFalse(self.backend.companion.status()['configured'])

    def test_locked_target_does_not_disconnect_current_game(self):
        ident = self.backend.create_profile('Ocupada')['created']
        lock = acquire_run_lock(self.root, ident)
        current = self.backend.service
        worker = self.backend.worker
        try:
            with self.assertRaises(RuntimeError):
                self.backend.switch_profile(ident)
            self.assertIs(self.backend.service, current)
            self.assertIs(self.backend.worker, worker)
            self.assertFalse(current.stop.is_set())
            self.assertEqual(self.backend.profile, 'principal')
        finally:
            lock.close()

    def test_http_port_cannot_be_rebound_by_another_local_instance(self):
        with self.assertRaises(OSError):
            LocalHTTPServer(self.backend.server.server_address, self.backend.server.RequestHandlerClass)
        with self.assertRaises(OSError):
            ThreadingHTTPServer(self.backend.server.server_address, self.backend.server.RequestHandlerClass)

    def test_switch_keeps_window_slot_reserved_for_obs(self):
        ident = self.backend.create_profile('Primera ventana')['created']
        self.backend.switch_profile(ident)
        profile, lock, slot, slot_lock = automatic_session(self.root)
        try:
            self.assertEqual(slot, 'segundo-jugador')
            self.assertEqual(profile, 'segundo-jugador')
            with self.assertRaises(RuntimeError):
                acquire_run_lock(self.root, 'window-principal')
            # Even with principal now free, a third window cannot reuse either output.
            with self.assertRaises(RuntimeError):
                automatic_session(self.root)
        finally:
            lock.close()
            slot_lock.close()

    def test_second_window_can_use_free_run_when_first_owns_secondary_run(self):
        self.backend.switch_profile('segundo-jugador')
        profile, lock, slot, slot_lock = automatic_session(self.root)
        try:
            self.assertEqual(slot, 'segundo-jugador')
            self.assertEqual(profile, 'principal')
        finally:
            lock.close()
            slot_lock.close()

    def test_target_startup_failure_restores_old_run_and_releases_target_lock(self):
        ident = self.backend.create_profile('Fallida')['created']
        old_service = self.backend.service

        def construct(path):
            if Path(path).parent.name == ident:
                raise OSError('No se pudo abrir el destino')
            return TrackerService(path)

        with patch('desktop.TrackerService', side_effect=construct):
            with self.assertRaises(OSError):
                self.backend.switch_profile(ident)
        self.assertEqual(self.backend.profile, 'principal')
        self.assertTrue(old_service.stop.is_set())
        self.assertFalse(self.backend.service.stop.is_set())
        self.assertTrue(self.backend.worker.is_alive())
        lock = acquire_run_lock(self.root, ident)
        lock.close()


if __name__ == '__main__':
    unittest.main()
