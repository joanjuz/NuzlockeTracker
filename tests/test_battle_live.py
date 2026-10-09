import json,unittest
from pathlib import Path
from tracker.battle import apply_battle_hp,BATTLE_START,LENGTH
class BattleTests(unittest.TestCase):
 def test_real_capture_before_during_after(self):
  for sample in json.loads((Path(__file__).parent/'fixtures/battle_moon.json').read_text()):
   class Reader:
    def read(self,a,n):
     assert a==BATTLE_START and n==LENGTH
     return bytes.fromhex(sample['raw_hex'])
   party,active=apply_battle_hp(Reader(),sample['party'],'Ultra Moon 1.0')
   self.assertEqual(active,sample['stage'].startswith('battle'))
   if active:self.assertEqual(party[0]['hp'],sample['visible_hp'])
   else:self.assertEqual(party,sample['party'])
 def test_reject_wrong_roster_and_zero_hp_with_released_memory(self):
  sample=json.loads((Path(__file__).parent/'fixtures/battle_moon.json').read_text())[2]
  class Reader:
   def read(self,a,n):return bytes.fromhex(sample['raw_hex'])
  sample['party'][0]['species_id']=1
  self.assertFalse(apply_battle_hp(Reader(),sample['party'],'Ultra Moon 1.0')[1])
  self.assertFalse(apply_battle_hp(Reader(),sample['party'],'Ultra Sun 1.0')[1])
 def test_legitimate_zero_hp_is_accepted(self):
  sample=json.loads((Path(__file__).parent/'fixtures/battle_moon.json').read_text())[2]
  data=bytearray.fromhex(sample['raw_hex']);data[4:6]=b'\0\0'
  class Reader:
   def read(self,a,n):return bytes(data)
  party,active=apply_battle_hp(Reader(),sample['party'],'Ultra Moon 1.0')
  self.assertTrue(active);self.assertEqual(party[0]['hp'],0)

 def test_same_battle_layout_is_valid_on_ultra_sun(self):
  sample=json.loads((Path(__file__).parent/'fixtures/battle_moon.json').read_text())[2]
  class Reader:
   def read(self,a,n):return bytes.fromhex(sample['raw_hex'])
  party,active=apply_battle_hp(Reader(),sample['party'],'Ultra Sun 1.0')
  self.assertTrue(active);self.assertEqual(party[0]['hp'],sample['visible_hp'])
