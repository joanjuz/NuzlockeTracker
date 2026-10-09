"""Native desktop launcher regression tests (no WebView2 required on CI)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop import (LocalBackend, app_home, auto_migrate_local_checkout,
                     import_legacy_runtime, legacy_runtime_candidates, main)


class DesktopTests(unittest.TestCase):
    def test_diagnostic_button_saves_to_file_without_browser_download(self):
        root = Path(__file__).resolve().parent.parent
        javascript = (root/'web'/'app.js').read_text(encoding='utf-8')
        html = (root/'web'/'index.html').read_text(encoding='utf-8')
        self.assertIn('/api/diagnostic/save', javascript)
        self.assertNotIn('URL.createObjectURL', javascript)
        self.assertIn('id="diagnostic-result"', html)

    def test_localappdata_persists_outside_distribution(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(app_home({'LOCALAPPDATA': temp}),
                             Path(temp) / 'PokemonTracker')

    def test_copy_legacy_runtime_without_overwriting_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / 'checkout' / 'runtime'
            old.mkdir(parents=True)
            (old / 'companion-credentials.json').write_text('{"token":"private-pair-token"}')
            secondary = old / 'profiles' / 'segundo-jugador'
            secondary.mkdir(parents=True)
            (secondary / 'state.json').write_text('{"game":"Ultra Moon 1.0"}')
            (old / 'pk3ds-templates.json').write_text('{"schema_version":1}')
            destination = root / 'LOCALAPPDATA' / 'PokemonTracker' / 'runtime'
            import_legacy_runtime(old, destination)
            self.assertEqual(json.loads((destination/'companion-credentials.json').read_text())['token'],
                             'private-pair-token')
            self.assertTrue((destination/'profiles'/'segundo-jugador'/'state.json').exists())
            with self.assertRaises(FileExistsError):
                import_legacy_runtime(old, destination)
            self.assertTrue((old / 'companion-credentials.json').exists())

    def test_find_checkout_when_exe_is_built_in_repo(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'server.py').write_text('# original')
            (root/'runtime').mkdir()
            (root/'runtime'/'state.json').write_text('{"game":"Ultra Moon 1.0"}')
            exe = root/'dist'/'PokemonTracker'/'PokemonTracker.exe'
            exe.parent.mkdir(parents=True)
            self.assertIn((root/'runtime').resolve(), list(legacy_runtime_candidates(exe)))
            home = root/'userdata'
            self.assertTrue(auto_migrate_local_checkout(home, exe))
            self.assertFalse(auto_migrate_local_checkout(home, exe))
            self.assertTrue((home/'runtime'/'state.json').exists())

    def test_both_profiles_open_distinct_servers_and_end_cleanly(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'runtime'
            principal = LocalBackend(root, 'principal').start()
            secondary = LocalBackend(root/'profiles'/'segundo-jugador',
                                     'segundo-jugador').start()
            try:
                self.assertNotEqual(principal.url, secondary.url)
                self.assertTrue(principal.url.startswith('http://127.0.0.1:'))
                from desktop import smoke_test
                self.assertTrue(smoke_test(principal))
                self.assertTrue(smoke_test(secondary))
                self.assertFalse((root/'companion-credentials.json').exists())
            finally:
                principal.close()
                secondary.close()
            self.assertFalse(principal.http_thread.is_alive())
            self.assertFalse(secondary.http_thread.is_alive())

    def test_native_backend_smoke_imports_only_on_windows(self):
        from desktop import smoke_test_native
        if os.name != 'nt':
            self.assertTrue(smoke_test_native())

    def test_headless_smoke_test_without_desktop_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'LOCALAPPDATA': folder}):
                self.assertEqual(main(['--smoke-test', '--profile', 'principal']), 0)
            self.assertTrue((Path(folder)/'PokemonTracker').is_dir())


if __name__ == '__main__':
    unittest.main()
