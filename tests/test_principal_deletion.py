"""La partida Principal se puede eliminar como las demás, sin tocar el resto de runtime."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from desktop import automatic_session
from tracker.run_profiles import RunProfileStore, acquire_run_lock

PRINCIPAL_FILES = ['state.json', 'state-progress.json', 'state-progress.json.bak',
                   'state-ultra-sun-progress.json', 'session-profile.json', 'obs-overlay.json',
                   'pk3ds-templates.json', 'companion-credentials.json', 'companion-cache.json']
PRINCIPAL_DIRS = ['obs-fonts', 'obs-hp-images', 'diagnosticos']


class PrincipalDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.runtime = self.home / 'runtime'
        self.runtime.mkdir()
        for name in PRINCIPAL_FILES:
            (self.runtime / name).write_text('principal')
        for name in PRINCIPAL_DIRS:
            (self.runtime / name).mkdir()
            (self.runtime / name / 'dato.bin').write_text('principal')
        (self.runtime / 'update-check.json').write_text('global')
        (self.runtime / 'nota-del-usuario.txt').write_text('no es de la partida')
        self.store = RunProfileStore(self.runtime)
        self.other = self.store.create('Ultra Luna Randomlocke')
        (self.store.require(self.other['id']) / 'state.json').write_text('otra partida')

    def tearDown(self):
        self.temp.cleanup()

    def test_deletes_only_principal_data_and_hides_it(self):
        self.store.delete('principal')
        for name in PRINCIPAL_FILES + PRINCIPAL_DIRS:
            self.assertFalse((self.runtime / name).exists(), name)
        self.assertEqual((self.runtime / 'update-check.json').read_text(), 'global')
        self.assertEqual((self.runtime / 'nota-del-usuario.txt').read_text(), 'no es de la partida')
        self.assertEqual((self.store.require(self.other['id']) / 'state.json').read_text(), 'otra partida')
        ids = [p['id'] for p in RunProfileStore(self.runtime).profiles()]
        self.assertNotIn('principal', ids)
        self.assertIn(self.other['id'], ids)
        with self.assertRaises(ValueError):
            self.store.require('principal')

    def test_open_principal_is_never_deleted(self):
        with acquire_run_lock(self.home, 'principal'):
            with self.assertRaises(RuntimeError):
                self.store.delete('principal')
        self.assertTrue((self.runtime / 'state.json').exists())

    def test_next_start_opens_another_run(self):
        self.store.delete('principal')
        profile, lock, slot, slot_lock = automatic_session(self.home)
        try:
            self.assertNotEqual(profile, 'principal')
            self.assertEqual(slot, 'principal')  # OBS keeps the same window/port slot
        finally:
            lock.close()
            slot_lock.close()

    def test_using_principal_again_brings_it_back(self):
        self.store.delete('principal')
        self.store.restore_principal()
        self.assertIn('principal', [p['id'] for p in self.store.profiles()])

    def test_refuses_links_before_deleting_anything(self):
        if sys.platform != 'win32':
            self.skipTest('uniones de directorio solo en Windows')
        outside = self.home / 'fuera'
        outside.mkdir()
        (outside / 'importante.txt').write_text('no borrar')
        (self.runtime / 'obs-fonts' / 'dato.bin').unlink()
        (self.runtime / 'obs-fonts').rmdir()
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.runtime / 'obs-fonts'), str(outside)],
                              capture_output=True)
        if made.returncode != 0:
            self.skipTest('no se pudo crear la unión')
        with self.assertRaises(ValueError):
            self.store.delete('principal')
        self.assertEqual((outside / 'importante.txt').read_text(), 'no borrar')
        self.assertTrue((self.runtime / 'state.json').exists(), 'nada se borra si hay un enlace')


if __name__ == '__main__':
    unittest.main()
