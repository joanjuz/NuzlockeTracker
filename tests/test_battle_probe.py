import unittest,struct,tempfile
from pathlib import Path
from tracker.battle_probe import initial_search,narrow
from tracker.profiles import ULTRA_SUN_10
from tracker.service import TrackerService
from tracker.reference import ReferenceData
class BattleProbeTests(unittest.TestCase):
 def test_hp_search_filters_static_copy(self):
  class Reader:
   def __init__(self):self.data=bytearray(65536)
   def read(self,a,n):return bytes(self.data[a:a+n])
  r=Reader();struct.pack_into('<H',r.data,100,80);struct.pack_into('<H',r.data,200,80)
  candidates,errors=initial_search(r,80,start=0,end=65536)
  self.assertEqual(candidates,[100,200]);self.assertEqual(errors,0)
  struct.pack_into('<H',r.data,200,43);self.assertEqual(narrow(r,candidates,43),[200])
 def test_sun_profile_and_history_isolation(self):
  self.assertFalse(ULTRA_SUN_10.verified)
  self.assertEqual(len(ReferenceData().routes('Ultra Sun 1.0')['routes']),90)
  class Reader:
   def close(self):pass
  with tempfile.TemporaryDirectory() as tmp:
   s=TrackerService(Path(tmp)/'state.json',connector_factory=lambda config:Reader())
   s.set_route_miss({'route':'8','missed':True})
   s.handle({'action':'connect','mode':'memory','game':'Ultra Sun 1.0'})
   self.assertEqual(s.snapshot()['game'],'Ultra Sun 1.0');self.assertEqual(s.snapshot()['progress']['missed_routes'],[])
   s.handle({'action':'connect','mode':'memory','game':'Ultra Moon 1.0'})
   self.assertEqual(s.snapshot()['progress']['missed_routes'],['8'])
