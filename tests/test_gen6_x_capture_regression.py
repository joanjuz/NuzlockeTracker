"""Real Pokémon X/Lime3DS addresses from 2026-10-10 diagnostic.

Address facts are corroborated by a complete, double-read PC and
three independent battle roster/HP samples. No personal PK6 bytes.
"""
import tempfile
import unittest
from pathlib import Path
from tracker.profiles import PROFILES
from tracker.service import TrackerService
from test_gen6_boxes import Gen6Memory
from test_gen6_battle import BattleMemory
from tracker.battle_gen6 import candidate_pairs


class XObservedMemory(Gen6Memory):
    def __init__(self,profile):
        super().__init__(profile)
        self.battle=BattleMemory('Pokémon X 1.0',hp=16)
        self.overworld_available=True

    def read(self,address,length):
        if (address,length)==(self.profile.party_address,2914):
            return self.party if self.overworld_available else bytes(2914)
        try:
            return self.battle.read(address,length)
        except ValueError:
            return super().read(address,length)


class PokemonXVerifiedCaptureTests(unittest.TestCase):
    def test_x_specific_box_address_and_other_games_unchanged(self):
        self.assertEqual(PROFILES['Pokémon X 1.0'].box_address,0x08C861B8)
        self.assertEqual(PROFILES['Pokémon Y 1.0'].box_address,0x08C861C8)
        self.assertEqual(PROFILES['Omega Ruby 1.0'].box_address,0x08C9A144)
        self.assertEqual(PROFILES['Alpha Sapphire 1.0'].box_address,0x08C9A144)

    def test_differential_hp_address_agrees_with_battle_roster_reader(self):
        battle_address,hp_reference=candidate_pairs('Pokémon X 1.0')[0]
        self.assertEqual(battle_address,0x08804A70)
        # Differential search across user-supplied 16 -> 8 -> 9 samples
        # returned 0x08203ED8, precisely the current-HP u16 address.
        self.assertEqual(hp_reference-264,0x08203ED8)

    def test_x_31_box_reads_and_three_live_hp_samples(self):
        profile=PROFILES['Pokémon X 1.0']
        for hp in (16,8,9):
            with self.subTest(hp=hp):
                mem=XObservedMemory(profile)
                mem.battle.current=hp
                with tempfile.TemporaryDirectory() as directory:
                    service=TrackerService(Path(directory)/'state.json')
                    service.config={'game':profile.name,'mode':'memory'}
                    service.factory=lambda cfg:mem
                    service.connect()
                    service.poll()
                    self.assertEqual(service.snapshot()['party'][0]['hp'],hp)
                    self.assertTrue(service.snapshot()['battle_hp'])
                    service.handle({'action':'scan'})
                    for _ in range(31):
                        service.poll()
                    state=service.snapshot()
                    self.assertTrue(state['box_verified'])
                    self.assertEqual(len(state['boxes']),31)
                    self.assertEqual(state['boxes']['1'][0]['species_id'],25)

    def test_battle_hp_falls_back_to_last_validated_party_if_overworld_disappears(self):
        profile=PROFILES['Pokémon X 1.0']
        mem=XObservedMemory(profile)
        with tempfile.TemporaryDirectory() as directory:
            service=TrackerService(Path(directory)/'state.json')
            service.config={'game':profile.name,'mode':'memory'}
            service.factory=lambda cfg:mem
            service.connect()
            service.poll()
            self.assertEqual(service.snapshot()['party'][0]['hp'],16)
            mem.overworld_available=False
            mem.battle.current=8
            service.poll()
            state=service.snapshot()
            self.assertTrue(state['battle_hp'])
            self.assertFalse(state['stale'])
            self.assertEqual(state['party'][0]['hp'],8)
            mem.battle.current=9
            service.poll()
            self.assertEqual(service.snapshot()['party'][0]['hp'],9)
