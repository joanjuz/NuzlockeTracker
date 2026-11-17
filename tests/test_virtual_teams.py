"""Saved virtual teams: validation, persistence, isolation per game and the local API."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from server import make_handler
from tracker.run_profiles import PRINCIPAL_FILE_PATTERNS
from tracker.service import TrackerService
from tracker.virtual_teams import MAX_TEAMS, VirtualTeamStore


def member(n, species='Pikachu', nickname='Chispa'):
    return {'id': f'33:{n}', 'species_id': 25, 'species': species, 'nickname': nickname}


class VirtualTeamStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state-virtual-teams.json'
        self.store = VirtualTeamStore(self.path, 'Ultra Moon 1.0', 'runtime')

    def save(self, name='Liga', members=None, **extra):
        return self.store.apply({'action': 'save', 'name': name, 'members': members or [member(1), member(2)], **extra})

    def test_save_keeps_name_order_dates_game_and_run(self):
        result = self.save(members=[member(3), member(1), member(2)])
        team = result['teams'][0]
        self.assertEqual(result['team'], team['id'])
        self.assertEqual(team['name'], 'Liga')
        self.assertEqual([m['id'] for m in team['members']], ['33:3', '33:1', '33:2'])
        self.assertEqual((team['game'], team['run']), ('Ultra Moon 1.0', 'runtime'))
        self.assertEqual(team['created'], team['modified'])
        self.assertRegex(team['created'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$')
        # A new store reads exactly what was written.
        reopened = VirtualTeamStore(self.path, 'Ultra Moon 1.0', 'runtime')
        self.assertEqual(reopened.view()['teams'], result['teams'])
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['schema_version'], 1)

    def test_update_rename_duplicate_and_delete(self):
        ident = self.save()['team']
        updated = self.save(name='Liga 2', members=[member(9)], id=ident)
        self.assertEqual(len(updated['teams']), 1)
        self.assertEqual(updated['teams'][0]['name'], 'Liga 2')
        self.assertEqual(updated['teams'][0]['members'], [member(9)])
        renamed = self.store.apply({'action': 'rename', 'id': ident, 'name': '  Final  '})
        self.assertEqual(renamed['teams'][0]['name'], 'Final')
        copy = self.store.apply({'action': 'duplicate', 'id': ident})
        self.assertEqual([t['name'] for t in copy['teams']], ['Final', 'Final (copia)'])
        self.assertNotEqual(copy['team'], ident)
        self.assertEqual(copy['teams'][1]['members'], copy['teams'][0]['members'])
        again = self.store.apply({'action': 'duplicate', 'id': ident})
        self.assertEqual(again['teams'][2]['name'], 'Final (copia 2)')
        with self.assertRaisesRegex(ValueError, 'confirmación'):
            self.store.apply({'action': 'delete', 'id': ident})
        self.assertEqual(len(self.store.view()['teams']), 3)
        deleted = self.store.apply({'action': 'delete', 'id': ident, 'confirm': True})
        self.assertEqual([t['name'] for t in deleted['teams']], ['Final (copia)', 'Final (copia 2)'])
        self.assertIsNone(deleted['team'])
        with self.assertRaisesRegex(ValueError, 'ya no existe'):
            self.store.apply({'action': 'rename', 'id': ident, 'name': 'X'})

    def test_invalid_requests_change_nothing(self):
        self.save()
        before = self.path.read_bytes()
        bad = [
            None, [], {'action': 'publish'},
            {'action': 'save', 'name': '', 'members': [member(1)]},
            {'action': 'save', 'name': 'x' * 61, 'members': [member(1)]},
            {'action': 'save', 'name': 'Liga', 'members': [member(5)]},
            {'action': 'save', 'name': 'liga', 'members': [member(5)]},
            {'action': 'save', 'name': 'B', 'members': []},
            {'action': 'save', 'name': 'B', 'members': [member(n) for n in range(7)]},
            {'action': 'save', 'name': 'B', 'members': [member(1), member(1)]},
            {'action': 'save', 'name': 'B', 'members': [{'id': '../x', 'species_id': 1}]},
            {'action': 'save', 'name': 'B', 'members': [{'id': '33:1', 'species_id': '25'}]},
            {'action': 'save', 'name': 'B', 'members': [{'id': '33:1', 'species_id': True}]},
            {'action': 'save', 'name': 'B', 'members': ['33:1']},
            {'action': 'save', 'name': 'B', 'members': [member(1)], 'id': 'missing'},
            {'action': 'duplicate', 'id': 'missing'},
        ]
        for request in bad:
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.store.apply(request)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(self.store.view()['teams']), 1)

    def test_stored_text_is_limited_and_extra_fields_are_dropped(self):
        noisy = {**member(1, species='S' * 90, nickname='A\x00B\nC'), 'token': 'secret', 'ot_id': 5}
        team = self.save(members=[noisy])['teams'][0]
        self.assertEqual(set(team['members'][0]), {'id', 'species_id', 'species', 'nickname'})
        self.assertEqual(len(team['members'][0]['species']), 40)
        self.assertEqual(team['members'][0]['nickname'], 'ABC')
        self.assertNotIn('secret', self.path.read_text(encoding='utf-8'))

    def test_team_limit(self):
        for n in range(MAX_TEAMS):
            self.save(name=f'Equipo {n}')
        with self.assertRaisesRegex(ValueError, 'máximo'):
            self.save(name='Uno más')
        with self.assertRaisesRegex(ValueError, 'máximo'):
            self.store.apply({'action': 'duplicate', 'id': self.store.view()['teams'][0]['id']})
        self.assertEqual(len(self.store.view()['teams']), MAX_TEAMS)

    def test_damaged_file_is_set_aside_not_overwritten(self):
        self.path.write_text('{"schema_version":1,"teams":[{"id":"x"}]}', encoding='utf-8')
        store = VirtualTeamStore(self.path, 'Ultra Moon 1.0')
        view = store.view()
        self.assertEqual(view['teams'], [])
        self.assertIn('dañado', view['notice'])
        copies = list(self.path.parent.glob('state-virtual-teams.json.corrupt-*'))
        self.assertEqual(len(copies), 1)
        self.assertIn('"id":"x"', copies[0].read_text(encoding='utf-8'))
        store.apply({'action': 'save', 'name': 'Nuevo', 'members': [member(1)]})
        self.assertNotIn('notice', store.view())

    def test_file_from_a_newer_version_is_kept_read_only(self):
        newer = '{"schema_version":2,"teams":[{"future":true}]}'
        self.path.write_text(newer, encoding='utf-8')
        store = VirtualTeamStore(self.path, 'Ultra Moon 1.0')
        view = store.view()
        self.assertTrue(view['read_only'])
        self.assertEqual(view['teams'], [])
        with self.assertRaisesRegex(ValueError, 'versión más nueva'):
            store.apply({'action': 'save', 'name': 'Liga', 'members': [member(1)]})
        self.assertEqual(self.path.read_text(encoding='utf-8'), newer)
        self.assertEqual(list(self.path.parent.glob('*.corrupt-*')), [])

    def test_failed_write_keeps_previous_teams(self):
        self.save()
        blocked = VirtualTeamStore(Path(self.temp.name) / 'state.json' / 'teams.json', 'Ultra Moon 1.0')
        (Path(self.temp.name) / 'state.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(OSError):
            blocked.apply({'action': 'save', 'name': 'Liga', 'members': [member(1)]})
        self.assertEqual(blocked.view()['teams'], [])
        self.assertEqual(len(self.store.view()['teams']), 1)


class VirtualTeamServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = TrackerService(self.root / 'state.json')
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service, 'test-token', None))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.port = server.server_port
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), worker.join(timeout=3)))

    def request(self, method, payload=None, authorized=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        headers = {'X-Tracker-Token': 'test-token'} if authorized else {}
        conn.request(method, '/api/teams', json.dumps(payload) if payload is not None else None, headers)
        response = conn.getresponse()
        status, body = response.status, json.loads(response.read() or b'{}')
        conn.close()
        return status, body

    def test_api_round_trip_requires_token_and_validates(self):
        self.assertEqual(self.request('GET'), (200, {'schema_version': 1, 'game': 'Ultra Moon 1.0', 'teams': [], 'limit': MAX_TEAMS}))
        payload = {'action': 'save', 'name': 'Liga', 'members': [member(1)]}
        self.assertEqual(self.request('POST', payload, authorized=False)[0], 403)
        self.assertEqual(self.request('GET')[1]['teams'], [])
        status, saved = self.request('POST', payload)
        self.assertEqual(status, 200)
        self.assertEqual(saved['teams'][0]['name'], 'Liga')
        status, error = self.request('POST', {'action': 'delete', 'id': saved['team']})
        self.assertEqual(status, 400)
        self.assertIn('confirmación', error['error'])
        self.assertEqual(self.request('POST', {'action': 'save', 'name': 'x', 'members': 'no'})[0], 400)
        self.assertEqual(self.request('POST', {'action': 'save', 'name': 'x' * 9000, 'members': [member(1)]})[0], 400)
        self.assertEqual(len(self.request('GET')[1]['teams']), 1)

    def test_teams_are_isolated_per_game_and_run_and_survive_restart(self):
        self.service.virtual_teams.apply({'action': 'save', 'name': 'Luna', 'members': [member(1)]})
        self.assertTrue((self.root / 'state-virtual-teams.json').is_file())
        # Another game of the same run uses its own file.
        self.service.open_progress(self.service.progress_suffix('Ultra Sun 1.0'), 'Ultra Sun 1.0')
        self.assertEqual(self.service.virtual_teams.view()['teams'], [])
        self.assertEqual(self.service.virtual_teams.view()['game'], 'Ultra Sun 1.0')
        self.service.virtual_teams.apply({'action': 'save', 'name': 'Sol', 'members': [member(2)]})
        self.assertTrue((self.root / 'state-ultra-sun-virtual-teams.json').is_file())
        # Another run (another folder) never sees them.
        other = TrackerService(self.root / 'profiles' / 'otra' / 'state.json')
        self.assertEqual(other.virtual_teams.view()['teams'], [])
        # Restart: the original game still has its team.
        again = TrackerService(self.root / 'state.json')
        self.assertEqual([t['name'] for t in again.virtual_teams.view()['teams']], ['Luna'])

    def test_teams_stay_out_of_snapshots_and_exports(self):
        self.service.virtual_teams.apply({'action': 'save', 'name': 'Equipo privado', 'members': [member(1, nickname='Secreto')]})
        snapshot = json.dumps(self.service.snapshot(), ensure_ascii=False)
        self.assertNotIn('Equipo privado', snapshot)
        self.assertNotIn('virtual', snapshot)

    def test_deleting_the_main_run_removes_its_teams(self):
        import fnmatch
        for name in ('state-virtual-teams.json', 'state-ultra-sun-virtual-teams.json', 'state-virtual-teams.json.tmp',
                     'state-virtual-teams.json.corrupt-1'):
            self.assertTrue(any(fnmatch.fnmatch(name, pattern) for pattern in PRINCIPAL_FILE_PATTERNS), name)


if __name__ == '__main__':
    unittest.main()
