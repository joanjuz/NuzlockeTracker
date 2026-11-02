"""The memory worker must survive disk locks, user command errors and retries."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tracker.service import TrackerService
from tracker.profiles import PROFILES


REAL_REPLACE = os.replace


def mon(ec=123, hp=100):
    return {'species_id': 448, 'nickname': 'Lucario', 'origin_version': 33,
            'encryption_constant': ec, 'met_location_id': 8, 'checksum_valid': True,
            'egg': False, 'hp': hp, 'max_hp': 100, 'moves': [0, 0, 0, 0]}


def stop_after(service, iterations):
    """Replace the idle wait of run() so the loop ends after N iterations."""
    calls = {'n': 0}

    def wait(timeout=None):
        calls['n'] += 1
        if calls['n'] >= iterations:
            service.stop.set()
        return service.stop.is_set()
    return patch.object(service.stop, 'wait', side_effect=wait)


class StatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'state.json'
        self.service = TrackerService(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def locked_state_json(self, failures=None):
        """os.replace fails for state.json (OneDrive/antivirus lock)."""
        count = {'n': 0}

        def replace(src, dst):
            if Path(dst) == self.path and (failures is None or count['n'] < failures):
                count['n'] += 1
                raise PermissionError(13, 'Acceso denegado', str(dst))
            return REAL_REPLACE(src, dst)
        return patch('tracker.service.os.replace', side_effect=replace), count

    def test_locked_state_json_publishes_revision_and_warning_without_raising(self):
        before = self.service.snapshot()['revision']
        locked, count = self.locked_state_json()
        with locked:
            self.assertTrue(self.service.update(stale=False))
        state = self.service.snapshot()
        self.assertGreater(state['revision'], before)
        self.assertFalse(state['stale'])
        self.assertIn('state.json', state['persist_warning'])
        # One quick retry, then a non-fatal warning.
        self.assertEqual(count['n'], 2)

    def test_single_transient_lock_is_retried_once(self):
        locked, count = self.locked_state_json(failures=1)
        with locked:
            self.assertTrue(self.service.update(stale=False))
        self.assertEqual(count['n'], 1)
        self.assertNotIn('persist_warning', self.service.snapshot())
        self.assertFalse(json.loads(self.path.read_text(encoding='utf-8'))['stale'])

    def test_warning_does_not_make_identical_updates_loop(self):
        locked, _ = self.locked_state_json()
        with locked:
            self.service.update(stale=False)
            revision = self.service.snapshot()['revision']
            self.assertFalse(self.service.update(stale=False))
        self.assertEqual(self.service.snapshot()['revision'], revision)

    def test_retry_persistence_recovers_and_clears_warning(self):
        locked, _ = self.locked_state_json()
        with locked:
            self.service.update(stale=False)
        self.assertFalse(self.path.exists())
        self.service.persist_retry_at = 0
        self.service.retry_persistence()
        self.assertNotIn('persist_warning', self.service.snapshot())
        saved = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertFalse(saved['stale'])
        self.assertNotIn('persist_warning', saved)

    def test_run_loop_survives_locked_state_json_during_error_handling(self):
        self.service.reader = object()
        self.service.next_box_refresh_at = float('inf')
        locked, _ = self.locked_state_json()
        with locked, patch.object(self.service, 'poll', side_effect=ValueError('RAM rota')), \
                stop_after(self.service, 2):
            self.service.run()
        self.assertEqual(self.service.snapshot()['connection']['message'], 'RAM rota')

    def test_run_loop_survives_failing_error_handler(self):
        self.service.reader = object()
        self.service.next_box_refresh_at = float('inf')
        polls = {'n': 0}

        def poll():
            polls['n'] += 1
            raise ValueError('RAM rota')
        with patch.object(self.service, 'poll', side_effect=poll), \
                patch.object(self.service, 'update', side_effect=RuntimeError('fallo interno')), \
                stop_after(self.service, 3):
            self.service.run()
        self.assertEqual(polls['n'], 3)


class CommandErrorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'state.json'
        self.service = TrackerService(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_duplicate_mark_dead_is_a_command_error_not_a_connection_error(self):
        self.service.update(party=[mon()] + [None] * 5, stale=False,
                            connection={'status': 'connected', 'message': 'Conectado'})
        self.service.commands.put({'action': 'mark_dead', 'key': '33:123'})
        self.service.commands.put({'action': 'mark_dead', 'key': '33:123'})
        with stop_after(self.service, 2):
            self.service.run()
        state = self.service.snapshot()
        self.assertEqual(state['connection'], {'status': 'connected', 'message': 'Conectado'})
        self.assertFalse(state['stale'])
        self.assertEqual(state['progress']['death_count'], 1)
        self.assertIn('ya está registrado', state['last_command_error']['message'])
        self.assertIsInstance(state['last_command_error']['at'], float)

    def test_connect_value_error_without_reader_waits_before_retrying(self):
        self.service.config = {'game': 'Ultra Moon 1.0', 'mode': 'memory', 'pid': None, 'port': 24689}
        with patch.object(self.service, 'connect', side_effect=ValueError('Proceso incorrecto')) as connect, \
                stop_after(self.service, 3):
            started = time.monotonic()
            self.service.run()
        connect.assert_called_once()
        self.assertGreaterEqual(self.service.retry_at, started + 2.5)
        self.assertEqual(self.service.snapshot()['connection']['status'], 'error')


class ProgressPersistenceInServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'state.json'

    def tearDown(self):
        self.directory.cleanup()

    def test_locked_progress_keeps_death_and_is_flushed_later(self):
        service = TrackerService(self.path)
        progress_file = service.progress.path

        def replace(src, dst):
            if Path(dst) == progress_file:
                raise PermissionError(13, 'Acceso denegado', str(dst))
            return REAL_REPLACE(src, dst)
        with patch('tracker.progress.os.replace', side_effect=replace):
            service.update(party=[mon(hp=0)] + [None] * 5, stale=False)
            service.update(party=[mon(hp=0)] + [None] * 5, stale=False)
        state = service.snapshot()
        self.assertEqual(state['progress']['death_count'], 1)
        self.assertIn('33:123', state['progress']['deaths'])
        self.assertIn('progreso', state['persist_warning'])
        self.assertTrue(service.progress.dirty)
        service.persist_retry_at = 0
        service.retry_persistence()
        self.assertFalse(service.progress.dirty)
        self.assertNotIn('persist_warning', service.snapshot())
        saved = json.loads(progress_file.read_text(encoding='utf-8'))
        self.assertEqual(saved['death_count'], 1)

    def test_corrupt_progress_is_reported_as_warning(self):
        progress_file = self.path.with_name('state-progress.json')
        progress_file.write_text('{roto', encoding='utf-8')
        service = TrackerService(self.path)
        self.assertEqual(service.progress.recovered_from, 'empty')
        self.assertIn('dañado', service.snapshot()['persist_warning'])


class SnapshotFieldsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'state.json'
        self.service = TrackerService(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_snapshot_fields_returns_isolated_copies_of_requested_keys(self):
        self.service.update(party=[mon()] + [None] * 5, stale=False)
        fields = self.service.snapshot_fields('party', 'stale', 'missing')
        # Missing keys are omitted so callers keep their .get() defaults.
        self.assertEqual(set(fields), {'party', 'stale'})
        fields['party'][0]['nickname'] = 'Otro'
        self.assertEqual(self.service.snapshot()['party'][0]['nickname'], 'Lucario')

    def test_gen7_poll_does_not_deep_copy_whole_state(self):
        self.service.reader = object()
        self.service.handle({'action': 'scan'})
        with patch('tracker.service.capture_party', return_value=b''), \
                patch('tracker.service.decode_party', return_value=[None] * 6), \
                patch('tracker.gen7_pc.read_box', return_value=bytes(6960)), \
                patch.object(self.service, 'snapshot', side_effect=AssertionError('snapshot completo')):
            for _ in range(32):
                self.service.poll()
        self.assertEqual(self.service.state['scan'], {'active': False, 'completed': 32})

    def test_gen6_poll_does_not_deep_copy_whole_state(self):
        from test_gen6_boxes import Gen6Memory
        game = 'Pokémon X 1.0'
        reader = Gen6Memory(PROFILES[game])
        self.service.factory = lambda cfg: reader
        self.service.config = {'game': game, 'mode': 'memory'}
        self.service.connect()
        with patch.object(self.service, 'snapshot', side_effect=AssertionError('snapshot completo')):
            for _ in range(31):
                self.service.poll()
        self.assertTrue(self.service.state['box_verified'])
        self.assertEqual(len(self.service.state['boxes']), 31)


if __name__ == '__main__':
    unittest.main()
