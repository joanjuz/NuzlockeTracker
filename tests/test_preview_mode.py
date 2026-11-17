"""A delivered preview must never fall back to the stable app's data home."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from desktop import main
from tracker.preview_mode import preview_home


class PreviewModeTests(unittest.TestCase):
    def marker(self, folder):
        exe = folder / 'PokemonTracker.exe'
        exe.write_bytes(b'test placeholder')
        (folder / 'TRACKER_PREVIEW.json').write_text(json.dumps({'format':'progressive-tracker-preview','version':1}), encoding='utf-8')
        return exe

    def test_frozen_marker_uses_only_sibling_test_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = self.marker(root)
            self.assertEqual(preview_home(exe, frozen=True), (root/'Datos-Prueba').resolve())
            self.assertIsNone(preview_home(exe, frozen=False))
            (root/'TRACKER_PREVIEW.json').unlink()
            self.assertIsNone(preview_home(exe, frozen=True))

    def test_invalid_marker_fails_closed_instead_of_using_production(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = self.marker(root)
            for content in ('{bad', '{"format":"other","version":1}', '{"format":"progressive-tracker-preview","version":2}'):
                (root/'TRACKER_PREVIEW.json').write_text(content, encoding='utf-8')
                with self.assertRaises(ValueError):
                    preview_home(exe, frozen=True)

    def test_preview_smoke_never_uses_stable_data_home(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = preview_home(self.marker(root), frozen=True)
            with patch('desktop.preview_home', return_value=home), patch('desktop.app_home', side_effect=AssertionError('Stable home must not be used')):
                self.assertEqual(main(['--smoke-test', '--profile', 'principal']), 0)
            self.assertTrue((home/'logs').is_dir())
            self.assertTrue((home/'layout'/'pokemon_1.png').is_file())
            self.assertFalse((root/'PokemonTracker').exists())

    def test_invalid_preview_startup_reports_error_without_creating_stable_data(self):
        with patch('desktop.preview_home', side_effect=ValueError('Marcador inválido')), patch('desktop.app_home', side_effect=AssertionError('No stable fallback')), patch('desktop.message_error') as message:
            self.assertEqual(main(['--smoke-test']), 1)
            message.assert_called_once()

    def test_interactive_preview_never_imports_legacy_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / 'Datos-Prueba'
            webview = Mock()
            with patch('desktop.preview_home', return_value=home), patch('desktop.auto_migrate_local_checkout', side_effect=AssertionError('No legacy import')), patch.dict('sys.modules', {'webview': webview}), patch('desktop.create_desktop_window'):
                self.assertEqual(main(['--profile', 'principal']), 0)
            webview.start.assert_called_once_with(gui='edgechromium', debug=False)


if __name__ == '__main__':
    unittest.main()
