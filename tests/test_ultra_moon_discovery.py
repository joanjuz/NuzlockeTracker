import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tracker.profiles import PROFILES
from tracker.service import TrackerService


class UltraMoonDiscoveryTests(unittest.TestCase):
    def connect_game(self, game):
        with tempfile.TemporaryDirectory() as folder:
            service = TrackerService(Path(folder) / 'state.json')
            service.config = {'game': game, 'mode': 'memory'}
            reader = SimpleNamespace(
                party_address=PROFILES[game].party_address + 0x2400,
                discovery_mode='dynamic', process=SimpleNamespace(discovery_report={}))
            with patch('tracker.service.LimeProcessMemory', return_value=reader) as factory:
                service.connect()
            return service.snapshot(), service.diagnostic, factory.call_args

    def test_ultra_moon_uses_dynamic_discovery_without_relabelling(self):
        state, diagnostic, call = self.connect_game('Ultra Moon 1.0')
        self.assertTrue(call.kwargs['dynamic'])
        self.assertEqual(call.kwargs['generation'], 7)
        self.assertEqual(state['game'], 'Ultra Moon 1.0')
        self.assertEqual(diagnostic['game'], 'Ultra Moon 1.0')
        self.assertEqual(diagnostic['party_address'], hex(PROFILES['Ultra Moon 1.0'].party_address + 0x2400))
        self.assertEqual(state['connection']['status'], 'connected')

    def test_ultra_sun_keeps_dynamic_discovery(self):
        state, diagnostic, call = self.connect_game('Ultra Sun 1.0')
        self.assertTrue(call.kwargs['dynamic'])
        self.assertEqual(state['game'], 'Ultra Sun 1.0')
        self.assertEqual(diagnostic['discovery_mode'], 'dynamic')
