"""Native Save As exports: safely chosen paths, no tokens or automatic save damage."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tracker.desktop_export import DesktopExportApi, export_payload, write_export
from tracker.service import TrackerService


class FileWindow:
    def __init__(self, selected):
        self.selected = selected
        self.calls = []

    def create_file_dialog(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.selected


class ExportsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.service = TrackerService(self.folder / 'runtime' / 'state.json')
        self.pokemon = {'species_id': 25, 'nickname': 'Chispa', 'origin_version': 33,
                        'encryption_constant': 1234, 'checksum_valid': True,
                        'hp': 50, 'max_hp': 50}
        self.service.update(
            party=[self.pokemon] + [None] * 5,
            boxes={'1': [self.pokemon] + [None] * 29},
            stale=False)
        self.service.diagnostic={'mode': 'dynamic', 'regions_scanned': 2880,
                                 'process': 'azahar.exe', 'pid': 1234}

    def tearDown(self):
        self.temp.cleanup()

    def test_session_export_contains_team_boxes_progress_not_secrets(self):
        payload = export_payload(self.service, 'session')
        self.assertEqual(payload['party'][0]['nickname'], 'Chispa')
        self.assertEqual(payload['boxes']['1'][0]['species_id'], 25)
        self.assertIn('progress', payload)
        self.assertIn('game', payload)
        self.assertNotIn('connection', payload)
        for secret in ('token', 'companion', 'credential', 'pid'):
            self.assertNotIn(secret, json.dumps(payload).lower())

    def test_diagnostic_exports_ram_details_not_pokemon_or_tokens(self):
        payload = export_payload(self.service, 'diagnostic')
        self.assertEqual(payload['diagnostic']['regions_scanned'], 2880)
        self.assertEqual(payload['diagnostic']['process'], 'azahar.exe')
        self.assertNotIn('party', json.dumps(payload))
        self.assertNotIn('boxes', json.dumps(payload))
        with self.assertRaises(ValueError):
            export_payload(self.service, 'private')

    def test_atomic_save_at_user_selected_location_only(self):
        path = self.folder/'Elegida por el usuario'
        actual = write_export(path, export_payload(self.service, 'session'))
        self.assertEqual(actual.suffix, '.json')
        self.assertTrue(actual.is_file())
        self.assertEqual(json.loads(actual.read_text(encoding='utf-8'))['party'][0]['nickname'], 'Chispa')
        self.assertFalse(path.exists())
        self.assertEqual(list(self.folder.glob('.tracker-*')), [])

    def test_native_save_dialog_and_cancel(self):
        chosen = self.folder/'MI SESION.json'
        window = FileWindow((str(chosen),))
        api = DesktopExportApi(self.service, window)
        fake = types.SimpleNamespace(FileDialog=types.SimpleNamespace(SAVE=30))
        with patch.dict(sys.modules, {'webview': fake}):
            result = api.save_export('session')
            self.assertEqual(result, {'saved': True, 'name': chosen.name})
            self.assertEqual(window.calls[0][0][0], 30)
            self.assertEqual(window.calls[0][1]['file_types'], ('Archivo JSON (*.json)',))
            window.selected=None
            self.assertEqual(api.save_export('diagnostic'), {'cancelled': True})
            self.assertFalse((self.folder/'diagnostico.json').exists())
        self.assertEqual(api.save_export('untrusted'), {'error': 'Exportación no permitida'})

    def test_saving_diagnostic_does_not_change_automatic_runtime(self):
        existing = self.service.output.read_bytes()
        selected = self.folder / 'ram.json'
        api = DesktopExportApi(self.service, FileWindow([str(selected)]))
        fake = types.SimpleNamespace(FileDialog=types.SimpleNamespace(SAVE=30))
        with patch.dict(sys.modules, {'webview': fake}):
            self.assertTrue(api.save_export('diagnostic')['saved'])
        self.assertEqual(self.service.output.read_bytes(), existing)
        self.assertEqual(json.loads(selected.read_text(encoding='utf-8'))['diagnostic']['pid'],1234)


if __name__ == '__main__':
    unittest.main()
