"""Battle HP validation must fail closed on any roster or health mismatch."""
import struct
import unittest
from tracker.battle_gen6 import apply_gen6_battle_hp,candidate_pairs
from tracker.pokemon import decode_party
from tracker.profiles import PROFILES
from test_gen6_compat import party_fixture

class BattleMemory:
 def __init__(self,game='Pokémon X 1.0',hp=9,maximum=23,level=7):
  self.game=game
  self.party_addr=PROFILES[game].party_address
  self.battle_addr,self.hpbase=candidate_pairs(game)[0]
  self.team=party_fixture(24 if game.startswith('Pokémon') else 26,address=self.party_addr)
  self.roster=party_fixture(24 if game.startswith('Pokémon') else 26,address=self.battle_addr)
  self.current=hp;self.maximum=maximum;self.level=level
  self.flip=False;self.counter=0
 def read(self,addr,length):
  if (addr,length)==(self.battle_addr,2914):return self.roster
  if (addr,length)==(self.hpbase-266,12):
   self.counter+=1
   health=self.current+1 if self.flip and self.counter%2==0 else self.current
   result=bytearray(12)
   struct.pack_into('<HH',result,0,self.maximum,health)
   result[8]=0
   result[10]=self.level
   return bytes(result)
  raise ValueError('La memoria fuera de batalla no coincide con ningún candidato')

class Gen6BattleTests(unittest.TestCase):
 def test_candidate_values_for_both_gen6_regions(self):
  self.assertEqual(len(candidate_pairs('Pokémon X 1.0')),2)
  self.assertEqual(len(candidate_pairs('Alpha Sapphire 1.0')),2)
  self.assertEqual(candidate_pairs('Ultra Moon 1.0'),())

 def test_read_hp_only_when_full_roster_identity_and_health_match(self):
  for game in ('Pokémon X 1.0','Omega Ruby 1.0'):
   with self.subTest(game=game):
    m=BattleMemory(game)
    party=decode_party(m.team,max_species=721)
    result,ok=apply_gen6_battle_hp(m,party,game,m.party_addr)
    self.assertTrue(ok)
    self.assertEqual(result[0]['hp'],9)
    self.assertEqual(result[0]['max_hp'],23)
    self.assertEqual(result[0]['hp_source'],'battle_gen6_candidate')
    self.assertEqual(m.counter,2)

 def test_rejects_health_jump_torn_reads_and_identity_mismatches(self):
  for bad in ('wrong_level','wrong_max','wrong_hp','changing','wrong_roster'):
   with self.subTest(bad=bad):
    m=BattleMemory()
    party=decode_party(m.team,max_species=721)
    if bad=='wrong_level':m.level=45
    elif bad=='wrong_max':m.maximum=40
    elif bad=='wrong_hp':m.current=99
    elif bad=='changing':m.flip=True
    elif bad=='wrong_roster':m.roster=party_fixture(species=37,address=m.battle_addr)
    result,ok=apply_gen6_battle_hp(m,party,m.game,m.party_addr)
    self.assertFalse(ok)
    self.assertEqual(result,party)

 def test_unknown_game_not_probed(self):
  m=BattleMemory()
  party=decode_party(m.team,max_species=721)
  result,ok=apply_gen6_battle_hp(m,party,'Ultra Moon 1.0',m.party_addr)
  self.assertFalse(ok)
  self.assertEqual(result,party)
