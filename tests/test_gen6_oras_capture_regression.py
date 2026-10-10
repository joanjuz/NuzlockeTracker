"""Regression for the verified Omega Ruby PC base in Lime3DS.

The 2026-10-10 user capture deposited a known Pokémon in Box1/Slot1.
Of six EC matches only 0x08C9A144 decoded as all 31 boxes.
Alpha Sapphire uses the shared candidate but awaits independent validation.
"""
import tempfile
import unittest
from pathlib import Path
from tracker.profiles import PROFILES
from tracker.service import TrackerService
from tracker.boxes import read_box, decode_box
from test_gen6_boxes import Gen6Memory

CONFIRMED_OR=0x08C9A144
OLD_ORAS=0x08C9E134

class OmegaRubyPCRegression(unittest.TestCase):
    def test_omega_ruby_real_address_is_not_naively_shifted_team_address(self):
        omega=PROFILES['Omega Ruby 1.0']
        alpha=PROFILES['Alpha Sapphire 1.0']
        self.assertEqual(omega.box_address,CONFIRMED_OR)
        self.assertEqual(alpha.box_address,CONFIRMED_OR)
        self.assertEqual(OLD_ORAS-CONFIRMED_OR,0x3ff0)
        self.assertEqual(omega.party_address,alpha.party_address)
        self.assertEqual(PROFILES['Pokémon X 1.0'].box_address,0x08C861B8)
        self.assertEqual(PROFILES['Pokémon Y 1.0'].box_address,0x08C861C8)
        self.assertEqual(PROFILES['Ultra Moon 1.0'].box_address,0x33015AB0)

    def test_omega_ruby_reads_31_boxes_and_keeps_party_intact(self):
        for name in ('Omega Ruby 1.0','Alpha Sapphire 1.0'):
            with self.subTest(game=name),tempfile.TemporaryDirectory() as dirname:
                profile=PROFILES[name]
                memory=Gen6Memory(profile)
                service=TrackerService(Path(dirname)/'state.json')
                service.factory=lambda cfg:memory
                service.config={'game':name,'mode':'memory'}
                service.connect()
                self.assertEqual(service.scan_next,1)
                service.poll()
                self.assertEqual(service.snapshot()['party'][0]['species_id'],25)
                self.assertFalse(service.snapshot()['box_verified'])
                first=decode_box(read_box(memory,1,profile.box_address,box_count=31),max_species=721)
                self.assertEqual(first[0]['species_id'],25)
                service.handle({'action':'scan'})
                for _ in range(30):service.poll()
                self.assertEqual(service.snapshot()['boxes'],{})
                service.poll()
                state=service.snapshot()
                self.assertTrue(state['box_verified'])
                self.assertEqual(state['scan']['completed'],31)
                self.assertEqual(len(state['boxes']),31)
                self.assertEqual(state['boxes']['1'][0]['species_id'],25)
                self.assertEqual(memory.read_count[0],3)

    def test_wrong_old_address_rejected_not_silently_published(self):
        profile=PROFILES['Omega Ruby 1.0']
        memory=Gen6Memory(profile)
        with self.assertRaises(ValueError):
            read_box(memory,1,OLD_ORAS,box_count=31)
