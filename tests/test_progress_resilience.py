"""Run history must survive corrupt files and transient disk locks."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tracker.progress import RunProgress


REAL_REPLACE = os.replace


def fainted(ec=77):
    return {'species_id': 25, 'origin_version': 33, 'encryption_constant': ec,
            'met_location_id': 8, 'checksum_valid': True, 'egg': False,
            'hp': 0, 'max_hp': 50}


class CorruptFileRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.folder = Path(self.directory.name)
        self.path = self.folder / 'state-progress.json'
        self.backup = self.folder / 'state-progress.json.bak'

    def tearDown(self):
        self.directory.cleanup()

    def corrupt_files(self):
        return sorted(self.folder.glob('state-progress.json.corrupt-*'))

    def test_deeply_nested_json_is_quarantined_instead_of_crashing(self):
        self.path.write_text('[' * 100000 + ']' * 100000, encoding='utf-8')
        run = RunProgress(self.path)
        self.assertEqual(run.recovered_from, 'empty')
        self.assertEqual(len(self.corrupt_files()), 1)

    def test_valid_file_is_not_flagged(self):
        RunProgress(self.path).mark_dead(fainted())
        run = RunProgress(self.path)
        self.assertIsNone(run.recovered_from)
        self.assertEqual(run.data['death_count'], 1)

    def test_unparseable_file_is_quarantined_and_backup_restored(self):
        first = RunProgress(self.path)
        first.mark_dead(fainted(1))
        first.mark_dead(fainted(2))  # previous good version becomes .bak
        self.assertTrue(self.backup.is_file())
        self.path.write_text('{"deaths": {', encoding='utf-8')
        run = RunProgress(self.path)
        self.assertEqual(run.recovered_from, 'backup')
        self.assertIn('33:1', run.data['deaths'])
        self.assertEqual(len(self.corrupt_files()), 1)
        self.assertEqual(self.corrupt_files()[0].read_text(encoding='utf-8'), '{"deaths": {')
        self.assertRegex(self.corrupt_files()[0].name, r'\.corrupt-\d{8}-\d{6}')

    def test_invalid_shape_without_backup_starts_empty(self):
        self.path.write_text(json.dumps({'deaths': [], 'missed_routes': []}), encoding='utf-8')
        run = RunProgress(self.path)
        self.assertEqual(run.recovered_from, 'empty')
        self.assertEqual(run.data['deaths'], {})
        self.assertEqual(run.data['death_count'], 0)
        self.assertEqual(len(self.corrupt_files()), 1)

    def test_non_object_json_starts_empty(self):
        self.path.write_text('[1, 2, 3]', encoding='utf-8')
        self.assertEqual(RunProgress(self.path).recovered_from, 'empty')

    def test_invalid_nested_record_with_corrupt_backup_starts_empty(self):
        self.path.write_text(json.dumps({'deaths': {}, 'missed_routes': [],
                                         'origins': {'x': 'route'}}), encoding='utf-8')
        self.backup.write_text('no es json', encoding='utf-8')
        run = RunProgress(self.path)
        self.assertEqual(run.recovered_from, 'empty')
        self.assertEqual(run.data['origins'], {})


class DurableSaveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'state-progress.json'

    def tearDown(self):
        self.directory.cleanup()

    def test_save_fsyncs_and_keeps_previous_good_file_as_backup(self):
        run = RunProgress(self.path)
        with patch('tracker.progress.os.fsync', wraps=os.fsync) as fsync:
            run.mark_dead(fainted(1))
        fsync.assert_called()
        self.assertFalse(self.path.with_name('state-progress.json.bak').exists())
        run.mark_dead(fainted(2))
        backup = json.loads(self.path.with_name('state-progress.json.bak').read_text(encoding='utf-8'))
        current = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(backup['death_count'], 1)
        self.assertEqual(current['death_count'], 2)

    def locked(self):
        def replace(src, dst):
            if Path(dst) == self.path:
                raise PermissionError(13, 'Acceso denegado', str(dst))
            return REAL_REPLACE(src, dst)
        return patch('tracker.progress.os.replace', side_effect=replace)

    def test_observe_keeps_death_in_memory_when_disk_is_locked(self):
        run = RunProgress(self.path)
        with self.locked():
            self.assertTrue(run.observe([fainted()]))
            self.assertFalse(run.observe([fainted()]))
        self.assertTrue(run.dirty)
        self.assertEqual(run.data['death_count'], 1)
        self.assertIn('33:77', run.data['deaths'])
        self.assertTrue(run.flush())
        self.assertFalse(run.dirty)
        self.assertEqual(RunProgress(self.path).data['death_count'], 1)

    def test_mark_dead_keeps_death_in_memory_when_disk_is_locked(self):
        run = RunProgress(self.path)
        with self.locked():
            self.assertTrue(run.mark_dead(fainted()))
            self.assertFalse(run.mark_dead(fainted()))
            self.assertFalse(run.flush())
        self.assertTrue(run.dirty)
        self.assertIn('Acceso denegado', run.last_save_error)
        self.assertEqual(run.data['death_count'], 1)
        self.assertTrue(run.flush())
        self.assertIsNone(run.last_save_error)
        self.assertFalse(list(Path(self.directory.name).glob('*.tmp')))

    def test_explicit_save_still_raises(self):
        run = RunProgress(self.path)
        with self.locked(), self.assertRaises(OSError):
            run.save()


if __name__ == '__main__':
    unittest.main()
