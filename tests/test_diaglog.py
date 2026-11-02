"""Registro de diagnóstico: útil para reportes, nunca con secretos."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from tracker import diaglog
from tracker.service import TrackerService


class RedactionTests(unittest.TestCase):
    def test_tokens_and_secrets_are_hidden(self):
        token = 'a1' * 24  # 48 hex, como el token del Worker
        session = 'Zx9_-' * 9  # 45 base64url, como la sesión directa
        line = diaglog.redact(f'Bearer {token} sesión={session} "token": "abc123" clave=CREATE_KEY_VALUE')
        self.assertNotIn(token, line)
        self.assertNotIn(session, line)
        self.assertNotIn('abc123', line)
        self.assertNotIn('CREATE_KEY_VALUE', line)
        self.assertIn('[oculto]', line)

    def test_ordinary_text_and_paths_are_kept(self):
        text = r'Conexión: connected · C:\Users\Ana\AppData\Local\PokemonTracker\layout pokemon 33:1234'
        self.assertEqual(diaglog.redact(text), text)


class FileAndRingTests(unittest.TestCase):
    def test_file_is_written_and_recent_lines_are_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = diaglog.setup(Path(temp) / 'logs', 'principal')
            self.assertIsNotNone(path)
            log = diaglog.get('test')
            log.warning('prueba de diagnóstico token=%s', 'f' * 48)
            for handler in diaglog._root.handlers:
                handler.flush()
            content = path.read_text(encoding='utf-8')
            self.assertIn('prueba de diagnóstico', content)
            self.assertNotIn('f' * 48, content)
            self.assertTrue(any('prueba de diagnóstico' in l for l in diaglog.recent(20)))
            # Release the file so the temporary folder can be removed on Windows.
            diaglog.close()


class ServiceLoggingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = TrackerService(Path(self.temp.name) / 'state.json')

    def tearDown(self):
        self.temp.cleanup()

    def test_connection_changes_and_deaths_are_logged_and_exported(self):
        self.service.update(connection={'status': 'error', 'message': 'Lime3DS no encontrado'})
        mon = {'species_id': 25, 'species': 'Pikachu', 'encryption_constant': 9, 'origin_version': 33,
               'checksum_valid': True, 'hp': 0, 'max_hp': 30}
        self.service.update(party=[mon] + [None] * 5, stale=False)
        lines = '\n'.join(diaglog.recent(50))
        self.assertIn('Lime3DS no encontrado', lines)
        self.assertIn('Muerte registrada', lines)
        exported = self.service.diagnostic_export()
        self.assertTrue(any('Muerte registrada' in l for l in exported['log']))
        json.dumps(exported)  # serialisable


class ConnectionLogThrottleTests(unittest.TestCase):
    def test_ram_search_progress_and_retry_loops_do_not_flood_the_log(self):
        with tempfile.TemporaryDirectory() as temp:
            service = TrackerService(Path(temp) / 'state.json')
            mark = 'marca-%f' % time.time()
            service.update(connection={'status': 'error', 'message': mark})
            for mb in range(0, 800, 4):
                service.update(connection={'status': 'connecting', 'message': f'Localizando RAM: {mb} MB'})
            for _ in range(10):  # emulator open, game not loaded: retry every 3 s
                service.update(connection={'status': 'connecting', 'message': 'Localizando RAM: 0 MB'})
                service.update(connection={'status': 'retrying', 'message': 'No se encontró la partida'})
            lines = diaglog.recent(400)
            start = max(i for i, line in enumerate(lines) if mark in line)
            new = [l for l in lines[start:] if 'Conexión:' in l]
            self.assertLessEqual(len(new), 4, new)
            self.assertTrue(any('No se encontró la partida' in l for l in new))


class StateWriteCoalescingTests(unittest.TestCase):
    def test_rapid_updates_write_once_then_flush_latest(self):
        with tempfile.TemporaryDirectory() as temp:
            service = TrackerService(Path(temp) / 'state.json')
            writes = []
            original = service.write_state

            def counting():
                writes.append(1)
                return original()
            service.write_state = counting
            service.last_state_write = 0.0
            for hp in range(10, 20):
                service.update(party=[{'species_id': 25, 'hp': hp, 'max_hp': 50}] + [None] * 5)
            self.assertEqual(len(writes), 1, 'los cambios de PS seguidos se agrupan')
            service.flush_state(force=True)
            saved = json.loads((Path(temp) / 'state.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['party'][0]['hp'], 19)
            self.assertFalse(service.state_dirty)

    def test_pending_write_is_flushed_when_due(self):
        with tempfile.TemporaryDirectory() as temp:
            service = TrackerService(Path(temp) / 'state.json')
            service.update(party=[{'species_id': 25, 'hp': 1, 'max_hp': 50}] + [None] * 5)
            service.update(party=[{'species_id': 25, 'hp': 2, 'max_hp': 50}] + [None] * 5)
            self.assertTrue(service.state_dirty)
            service.last_state_write = time.monotonic() - 5
            service.flush_state()
            saved = json.loads((Path(temp) / 'state.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['party'][0]['hp'], 2)


if __name__ == '__main__':
    unittest.main()
