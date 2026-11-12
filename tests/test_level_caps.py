"""Manual level caps per run and game: model, persistence, commands and unchanged contracts."""
import copy
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from companion.snapshot import snapshot
from server import make_handler
from tracker.overlay import OverlayManager
from tracker.progress import (KEEP_CURRENT, MAX_STAGES, RunProgress, level_caps_view,
                              normalized_stages)
from tracker.service import TrackerService

from test_companion import state as companion_state
from test_game_data import document as dgd_document


def stages(*caps, names=None):
    return [{'name': (names or [f'Etapa {i + 1}' for i in range(len(caps))])[i], 'cap': cap}
            for i, cap in enumerate(caps)]


def mon(level=40, hp=50, ec=1234):
    return {'species_id': 448, 'species': 'Lucario', 'level': level, 'hp': hp, 'max_hp': 120,
            'encryption_constant': ec, 'origin_version': 33, 'met_location_id': 8,
            'checksum_valid': True, 'egg': False}


class LevelCapsModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state-progress.json'

    def progress(self):
        return RunProgress(self.path)

    def history(self):
        """A run with deaths, encounters and route marks, written by the current format."""
        data = RunProgress.empty_data()
        data['deaths'] = {'33:1': {'pokemon': mon(ec=1), 'recorded_at': '2026-11-01T00:00:00+00:00'}}
        data['missed_routes'] = ['10']
        data['encounters'] = {'33:2': {'species_id': 25, 'met_location_id': 8}}
        data['route_marks'] = {'33:3': {'kind': 'trade', 'pokemon': {'species_id': 133}}}
        data['death_count'] = 1
        return data

    def test_old_run_without_level_caps_loads_unchanged(self):
        old = self.history()
        self.path.write_text(json.dumps(old), encoding='utf-8')
        progress = self.progress()
        self.assertNotIn('level_caps', progress.data)
        self.assertFalse(progress.level_caps_isolated)
        self.assertEqual(progress.data['deaths'], old['deaths'])
        self.assertEqual(level_caps_view(progress.data)['status'], 'none')
        progress.set_miss('11', True)
        self.assertNotIn('level_caps', json.loads(self.path.read_text(encoding='utf-8')))

    def test_valid_stages_get_stable_ids_and_survive_restart(self):
        progress = self.progress()
        self.assertTrue(progress.set_level_caps(stages(14, 20, 25)))
        saved = progress.data['level_caps']
        ids = [s['id'] for s in saved['stages']]
        self.assertEqual(len(set(ids)), 3)
        self.assertTrue(progress.set_current_stage(ids[1]))
        reopened = self.progress()
        self.assertEqual(reopened.data['level_caps']['stages'], progress.data['level_caps']['stages'])
        view = level_caps_view(reopened.data)
        self.assertEqual((view['status'], view['current'], view['current_index'], view['current_cap'], view['total']),
                         ('ok', ids[1], 1, 20, 3))
        self.assertTrue(view['show'])
        # Editing a name keeps every id.
        edited = copy.deepcopy(reopened.data['level_caps']['stages'])
        edited[0]['name'] = 'Primer gimnasio'
        reopened.set_level_caps(edited)
        self.assertEqual([s['id'] for s in reopened.data['level_caps']['stages']], ids)

    def test_no_default_caps_are_invented(self):
        progress = self.progress()
        self.assertNotIn('level_caps', progress.data)
        progress.set_level_caps_shown(False)
        self.assertEqual(progress.data['level_caps']['stages'], [])
        self.assertIsNone(level_caps_view(progress.data)['current_cap'])

    def test_invalid_stages_are_rejected_and_leave_the_data_intact(self):
        progress = self.progress()
        progress.set_level_caps(stages(10, 20))
        before = copy.deepcopy(progress.data)
        disk = self.path.read_bytes()
        too_many = stages(*([5] * (MAX_STAGES + 1)))
        cases = [
            too_many, 'not a list', [None], [{'name': '', 'cap': 5}], [{'name': '   ', 'cap': 5}],
            [{'name': 'x' * 61, 'cap': 5}], [{'name': 'a\nb', 'cap': 5}], [{'name': 'a b', 'cap': 5}],
            [{'name': 5, 'cap': 5}], [{'name': 'A', 'cap': 0}], [{'name': 'A', 'cap': 101}],
            [{'name': 'A', 'cap': True}], [{'name': 'A', 'cap': 1.5}], [{'name': 'A', 'cap': '5'}],
            [{'name': 'A', 'cap': 5, 'extra': 1}], [{'id': 'bad id!', 'name': 'A', 'cap': 5}],
            [{'id': 'same', 'name': 'A', 'cap': 5}, {'id': 'same', 'name': 'B', 'cap': 6}],
        ]
        for case in cases:
            with self.subTest(case=str(case)[:60]):
                with self.assertRaises(ValueError):
                    progress.set_level_caps(case)
                self.assertEqual(progress.data, before)
                self.assertEqual(self.path.read_bytes(), disk)
        with self.assertRaises(ValueError):
            progress.set_level_caps(stages(10), current='missing')
        with self.assertRaises(ValueError):
            progress.set_current_stage('missing')
        with self.assertRaises(ValueError):
            progress.set_level_caps_shown('yes')
        self.assertEqual(progress.data, before)

    def test_boundaries_are_accepted(self):
        progress = self.progress()
        accepted = stages(*([1] * (MAX_STAGES - 1) + [100]), names=['x' * 60] + ['y'] * (MAX_STAGES - 1))
        self.assertTrue(progress.set_level_caps(accepted))
        self.assertEqual(len(progress.data['level_caps']['stages']), MAX_STAGES)
        self.assertEqual(normalized_stages([{'name': '  Liga  ', 'cap': 50}], True), [{'name': 'Liga', 'cap': 50}])

    def test_reordering_keeps_the_current_stage_by_id(self):
        progress = self.progress()
        progress.set_level_caps(stages(10, 20, 30))
        a, b, c = progress.data['level_caps']['stages']
        progress.set_current_stage(b['id'])
        progress.set_level_caps([c, a, b])
        view = level_caps_view(progress.data)
        self.assertEqual((view['current'], view['current_index'], view['current_cap']), (b['id'], 2, 20))
        self.assertIsNone(view['removed_current'])

    def test_removing_the_current_stage_leaves_no_current_stage(self):
        progress = self.progress()
        progress.set_level_caps(stages(10, 20, 30))
        a, b, c = progress.data['level_caps']['stages']
        progress.set_current_stage(b['id'])
        progress.set_level_caps([a, c])
        view = level_caps_view(progress.data)
        # Neither the previous nor the next stage is picked silently.
        self.assertIsNone(view['current'])
        self.assertIsNone(view['current_cap'])
        self.assertEqual(view['removed_current'], b)
        reopened = self.progress()
        self.assertEqual(level_caps_view(reopened.data)['removed_current'], b)
        reopened.set_current_stage(c['id'])
        self.assertIsNone(level_caps_view(reopened.data)['removed_current'])
        # Removing it while choosing another one in the same command: no notice.
        reopened.set_level_caps([a], current=a['id'])
        self.assertEqual((level_caps_view(reopened.data)['current'], level_caps_view(reopened.data)['removed_current']),
                         (a['id'], None))
        # Removing every stage clears the current one too.
        reopened.set_level_caps([])
        self.assertEqual(level_caps_view(reopened.data)['removed_current'], a)
        self.assertFalse(level_caps_view(reopened.data)['configured'])

    def test_change_current_stage_and_new_ids_do_not_reuse_removed_ones(self):
        progress = self.progress()
        progress.set_level_caps(stages(10, 20))
        a, b = progress.data['level_caps']['stages']
        progress.set_current_stage(a['id'])
        self.assertFalse(progress.set_current_stage(a['id']))
        self.assertTrue(progress.set_current_stage(None))
        self.assertIsNone(level_caps_view(progress.data)['current'])
        progress.set_current_stage(b['id'])
        progress.set_level_caps([a, {'name': 'Nueva', 'cap': 30}])
        ids = [s['id'] for s in progress.data['level_caps']['stages']]
        self.assertEqual(ids[0], a['id'])
        self.assertNotIn(ids[1], (a['id'], b['id']))

    def test_decreasing_caps_are_allowed_and_reported(self):
        progress = self.progress()
        self.assertTrue(progress.set_level_caps(stages(20, 15, 30, 30, 5)))
        s = progress.data['level_caps']['stages']
        self.assertEqual(level_caps_view(progress.data)['decreasing'], [s[1]['id'], s[4]['id']])

    def test_show_option(self):
        progress = self.progress()
        progress.set_level_caps(stages(10))
        self.assertTrue(progress.set_level_caps_shown(False))
        self.assertFalse(self.progress().data['level_caps']['show'])
        self.assertFalse(progress.set_level_caps_shown(False))

    def test_damaged_block_is_isolated_without_quarantining_the_history(self):
        damaged_blocks = [
            'texto', [], {'version': 1}, {'version': 'x', 'stages': []},
            {'version': 1, 'stages': [{'id': 'a', 'name': 'A', 'cap': 500}], 'current': None, 'show': True},
            {'version': 1, 'stages': [{'id': 'a', 'name': 'A', 'cap': 5}], 'current': 'zz', 'show': True},
            {'version': 1, 'stages': [], 'current': None, 'show': 'si'},
            {'version': 1, 'stages': [], 'current': None, 'show': True, 'unknown': 1},
        ]
        for block in damaged_blocks:
            with self.subTest(block=str(block)[:60]):
                for leftover in self.path.parent.glob('*'):
                    leftover.unlink()
                data = self.history()
                data['level_caps'] = block
                self.path.write_text(json.dumps(data), encoding='utf-8')
                progress = self.progress()
                self.assertIsNone(progress.recovered_from)
                self.assertTrue(progress.level_caps_isolated)
                self.assertEqual(progress.data['deaths'], data['deaths'])
                self.assertEqual(progress.data['encounters'], data['encounters'])
                self.assertEqual(progress.data['route_marks'], data['route_marks'])
                self.assertEqual(progress.data['missed_routes'], ['10'])
                self.assertNotIn('level_caps', progress.data)
                self.assertEqual(progress.data['level_caps_rejected']['data'], block)
                self.assertEqual(list(self.path.parent.glob('*.corrupt*')), [])
                self.assertTrue(level_caps_view(progress.data)['rejected_kept'])
                # New caps can be configured; the rejected copy is kept and the marker never reaches disk.
                progress.set_level_caps(stages(12))
                saved = json.loads(self.path.read_text(encoding='utf-8'))
                self.assertEqual(saved['level_caps_rejected']['data'], block)
                self.assertNotIn('_level_caps_isolated_now', saved)
                reopened = self.progress()
                self.assertFalse(reopened.level_caps_isolated)
                self.assertEqual(reopened.data['deaths'], data['deaths'])

    def test_unreadable_file_keeps_the_existing_backup_path(self):
        progress = self.progress()
        progress.set_level_caps(stages(10))
        progress.set_level_caps(stages(10, 20))
        self.assertTrue(progress.backup_path.is_file())
        self.path.write_text('{roto', encoding='utf-8')
        recovered = self.progress()
        self.assertEqual(recovered.recovered_from, 'backup')
        self.assertEqual([s['cap'] for s in recovered.data['level_caps']['stages']], [10])

    def test_block_from_a_newer_tracker_is_kept_and_not_edited(self):
        data = self.history()
        future = {'version': 2, 'stages': [{'id': 'a', 'name': 'A', 'cap': 5, 'trigger': 'badge-1'}], 'rules': {'x': 1}}
        data['level_caps'] = future
        self.path.write_text(json.dumps(data), encoding='utf-8')
        progress = self.progress()
        self.assertFalse(progress.level_caps_isolated)
        self.assertEqual(level_caps_view(progress.data)['status'], 'unsupported')
        for change in (lambda: progress.set_level_caps(stages(5)), lambda: progress.set_current_stage(None),
                       lambda: progress.set_level_caps_shown(False)):
            with self.assertRaisesRegex(ValueError, 'versión más nueva'):
                change()
        progress.set_miss('11', True)
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['level_caps'], future)

    def test_caps_never_feed_death_detection(self):
        progress = self.progress()
        progress.set_level_caps(stages(5))
        progress.set_current_stage(progress.data['level_caps']['stages'][0]['id'])
        self.assertFalse(progress.observe([mon(level=90, hp=50)] + [None] * 5))
        self.assertEqual(progress.data['deaths'], {})

    def test_keep_current_is_the_default(self):
        self.assertIs(RunProgress.set_level_caps.__defaults__[0], KEEP_CURRENT)


class LevelCapsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_commands_update_state_and_session_export(self):
        service = TrackerService(self.root / 'run-a' / 'state.json')
        self.assertEqual(service.snapshot()['level_caps']['status'], 'none')
        service.handle({'action': 'level_caps_set', 'stages': stages(14, 20)})
        first = service.snapshot()['level_caps']['stages'][0]['id']
        service.handle({'action': 'level_caps_current', 'stage': first})
        service.handle({'action': 'level_caps_show', 'show': False})
        view = service.snapshot()['level_caps']
        self.assertEqual((view['current'], view['current_cap'], view['show']), (first, 14, False))
        exported = service.session_export()
        self.assertEqual(exported['progress']['level_caps']['current'], first)
        self.assertEqual(exported['schema_version'], 1)

    def test_invalid_command_reports_error_and_keeps_data(self):
        service = TrackerService(self.root / 'state.json')
        service.handle({'action': 'level_caps_set', 'stages': stages(10)})
        before = copy.deepcopy(service.progress.data)
        for cmd in ({'action': 'level_caps_set', 'stages': stages(0)},
                    {'action': 'level_caps_current', 'stage': 'missing'},
                    {'action': 'level_caps_current'},
                    {'action': 'level_caps_show', 'show': 1}):
            with self.subTest(cmd=cmd):
                service.handle_command(cmd)
                self.assertEqual(service.progress.data, before)
                self.assertEqual(service.snapshot()['last_command_error']['action'], cmd['action'])

    def test_runs_and_games_are_isolated_and_persist(self):
        run_a = TrackerService(self.root / 'run-a' / 'state.json')
        run_b = TrackerService(self.root / 'run-b' / 'state.json')
        run_a.handle({'action': 'level_caps_set', 'stages': stages(14)})
        self.assertEqual(run_b.snapshot()['level_caps']['status'], 'none')
        self.assertEqual(TrackerService(self.root / 'run-a' / 'state.json').snapshot()['level_caps']['total'], 1)
        # Another game of the same run uses its own progress file.
        def other_game(game):
            suffix = TrackerService.progress_suffix(game)
            return RunProgress(run_a.output.with_name(run_a.output.stem + suffix + '-progress.json'))
        sun, oras = other_game('Ultra Sun 1.0'), other_game('Omega Ruby 1.0')
        self.assertNotEqual(sun.path, run_a.progress.path)
        self.assertNotIn('level_caps', sun.data)
        self.assertNotIn('level_caps', oras.data)
        sun.set_level_caps(stages(30))
        self.assertEqual([s['cap'] for s in run_a.progress.data['level_caps']['stages']], [14])
        self.assertEqual([s['cap'] for s in TrackerService(self.root / 'run-a' / 'state.json').progress.data['level_caps']['stages']], [14])
        self.assertNotIn('level_caps', other_game('Omega Ruby 1.0').data)

    def test_damaged_block_produces_a_warning_not_a_quarantine(self):
        path = self.root / 'state.json'
        service = TrackerService(path)
        progress_path = service.progress.path
        data = RunProgress.empty_data()
        data['deaths'] = {'33:1': {'pokemon': mon(ec=1), 'recorded_at': 'x'}}
        data['level_caps'] = {'version': 1, 'stages': 'roto'}
        progress_path.write_text(json.dumps(data), encoding='utf-8')
        reopened = TrackerService(path)
        warning = reopened.snapshot().get('persist_warning') or ''
        self.assertIn('límites de nivel', warning)
        self.assertNotIn('dañado y no había copia', warning)
        self.assertIn('33:1', reopened.snapshot()['progress']['deaths'])

    def test_soullink_snapshot_is_unchanged(self):
        base = companion_state()
        with_caps = copy.deepcopy(base)
        with_caps['progress']['level_caps'] = {'version': 1, 'stages': [{'id': 'a', 'name': 'A', 'cap': 5}],
                                               'current': 'a', 'show': True, 'updated_at': None, 'removed_current': None}
        with_caps['progress']['level_caps_rejected'] = {'rejected_at': 'x', 'data': {'secret': 1}}
        with_caps['level_caps'] = level_caps_view(with_caps['progress'])
        self.assertEqual(json.dumps(snapshot(base), sort_keys=True), json.dumps(snapshot(with_caps), sort_keys=True))

    def test_obs_public_state_is_unchanged(self):
        service = TrackerService(self.root / 'runtime' / 'state.json')
        layout = self.root / 'layout'
        layout.mkdir()
        manager = OverlayManager(service, self.root / 'runtime', layout)
        service.update(party=[mon()] + [None] * 5, stale=False, connection={'status': 'connected', 'message': ''})
        before = manager.public_state()
        service.handle({'action': 'level_caps_set', 'stages': stages(5, 10)})
        service.handle({'action': 'level_caps_current', 'stage': service.snapshot()['level_caps']['stages'][0]['id']})
        after = manager.public_state()
        before.pop('revision')
        after.pop('revision')
        self.assertEqual(before, after)
        self.assertNotIn('level_caps', json.dumps(after))

    def test_definitive_game_data_import_coexists(self):
        service = TrackerService(self.root / 'run-a' / 'state.json')
        preview = service.preview_game_data(json.dumps(dgd_document()), 'Ultra Moon 1.0')
        service.apply_game_data(preview['previewToken'], 'Ultra Moon 1.0', True)
        status = service.snapshot()['game_data']
        service.handle({'action': 'level_caps_set', 'stages': stages(20)})
        reopened = TrackerService(self.root / 'run-a' / 'state.json')
        self.assertEqual(reopened.snapshot()['game_data'], status)
        self.assertEqual(reopened.snapshot()['level_caps']['total'], 1)
        self.assertNotIn('level_caps', json.dumps(reopened.game_data.document))

    def test_demo_service_starts_without_caps_and_accepts_commands(self):
        from tracker.demo import DemoService
        demo = DemoService(self.root / 'demo' / 'state.json')
        self.assertEqual(demo.snapshot()['level_caps']['status'], 'none')
        demo.handle({'action': 'level_caps_set', 'stages': stages(50)})
        self.assertEqual(demo.snapshot()['level_caps']['total'], 1)


class LevelCapsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = TrackerService(Path(self.temp.name) / 'state.json')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service, 'test-token'))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def post(self, payload):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request('POST', '/api/command', json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                     {'X-Tracker-Token': 'test-token', 'Content-Type': 'application/json'})
        response = conn.getresponse()
        result = response.status, json.loads(response.read() or b'{}')
        conn.close()
        return result

    def test_invalid_commands_answer_400_and_queue_nothing(self):
        self.service.progress.set_level_caps(stages(10))
        before = copy.deepcopy(self.service.progress.data)
        for payload in ({'action': 'level_caps_set', 'stages': stages(101)},
                        {'action': 'level_caps_set', 'stages': stages(10), 'current': 'missing'},
                        {'action': 'level_caps_current', 'stage': 'missing'},
                        {'action': 'level_caps_show', 'show': 'si'},
                        {'action': 'level_caps_set', 'stages': [{'name': 'x' * 61, 'cap': 5}]}):
            with self.subTest(payload=str(payload)[:60]):
                status, body = self.post(payload)
                self.assertEqual(status, 400)
                self.assertIn('error', body)
        self.assertTrue(self.service.commands.empty())
        self.assertEqual(self.service.progress.data, before)

    def test_full_list_may_exceed_the_general_command_size(self):
        full = stages(*range(1, MAX_STAGES + 1), names=['Ñandú ' + 'á' * 50] * MAX_STAGES)
        self.assertGreater(len(json.dumps({'action': 'level_caps_set', 'stages': full}, ensure_ascii=False).encode()), 4096)
        self.assertEqual(self.post({'action': 'level_caps_set', 'stages': full})[0], 202)
        queued = self.service.commands.get_nowait()
        self.service.handle(queued)
        self.assertEqual(self.service.snapshot()['level_caps']['total'], MAX_STAGES)
        # Every other command keeps the 4096-byte limit.
        status, body = self.post({'action': 'route_miss', 'route': '1', 'missed': True, 'pad': 'x' * 5000})
        self.assertEqual((status, body.get('error')), (400, 'Tamaño inválido'))


if __name__ == '__main__':
    unittest.main()
