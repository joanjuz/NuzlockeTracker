import copy,tempfile,unittest
from pathlib import Path
from tracker.demo import DemoService
from tracker.service import TrackerService

class ProgressTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'demo-state.json';self.service=DemoService(self.path)
 def tearDown(self):self.tmp.cleanup()
 def test_first_death_persists_without_duplicates_after_healing_or_evolution(self):
  self.service.scenario('damage');deaths=self.service.snapshot()['progress']['deaths'];self.assertEqual(len(deaths),1)
  self.service.scenario('normal');self.service.scenario('damage')
  party=copy.deepcopy(self.service.team);party[0].update(hp=0,nickname='Otro mote',species_id=1,slot=6)
  self.service.update(party=party,stale=False)
  self.assertEqual(self.service.snapshot()['progress']['deaths'],deaths)
  self.assertEqual(DemoService(self.path).snapshot()['progress']['deaths'],deaths)
  self.assertEqual(TrackerService(self.path.with_name('state.json')).snapshot()['progress']['deaths'],{})
 def test_only_valid_live_party_is_observed(self):
  party=copy.deepcopy(self.service.team);party[0]['hp']=0
  self.service.update(party=party,stale=True);self.assertFalse(self.service.snapshot()['progress']['deaths'])
  for change in ({'max_hp':None},{'egg':True},{'checksum_valid':False}):
   invalid=copy.deepcopy(party);invalid[0].update(change);self.service.update(party=invalid,stale=False)
   self.assertFalse(self.service.snapshot()['progress']['deaths'])
  self.service.update(boxes={'1':party});self.assertFalse(self.service.snapshot()['progress']['deaths'])
  self.service.update(party=party,stale=False);self.assertEqual(len(self.service.snapshot()['progress']['deaths']),1)
 def test_miss_reversible_persistent_and_validated(self):
  cmd={'action':'route_miss','route':'8','missed':True};self.service.handle(cmd);self.service.handle(cmd)
  self.assertEqual(DemoService(self.path).snapshot()['progress']['missed_routes'],['8'])
  self.service.handle(dict(cmd,missed=False));self.assertEqual(DemoService(self.path).snapshot()['progress']['missed_routes'],[])
  for invalid in (dict(cmd,route='unknown'),dict(cmd,missed='false')):
   with self.assertRaises(ValueError):self.service.handle(invalid)
 def test_revive_waits_for_health_before_next_death_and_survives_restart(self):
  self.service.scenario('damage');key=next(iter(self.service.snapshot()['progress']['deaths']))
  self.service.handle({'action':'revive','key':key})
  self.assertFalse(self.service.snapshot()['progress']['deaths'])
  self.service.scenario('damage');self.assertFalse(self.service.snapshot()['progress']['deaths'])
  reloaded=TrackerService(self.path)
  damaged=copy.deepcopy(self.service.snapshot()['party'])
  reloaded.update(party=damaged,stale=False);self.assertFalse(reloaded.snapshot()['progress']['deaths'])
  healed=copy.deepcopy(damaged);healed[0]['hp']=1
  reloaded.update(party=healed,stale=False)
  reloaded.update(party=damaged,stale=False)
  self.assertEqual(len(reloaded.snapshot()['progress']['deaths']),1)
 def test_revive_already_healed_can_die_again_immediately(self):
  self.service.scenario('damage');key=next(iter(self.service.snapshot()['progress']['deaths']))
  self.service.scenario('normal');self.service.handle({'action':'revive','key':key})
  self.assertFalse(self.service.snapshot()['progress']['deaths'])
  self.service.scenario('damage');self.assertIn(key,self.service.snapshot()['progress']['deaths'])
 def test_revive_validates_key(self):
  for key in (None,{},'not-registered'):
   with self.assertRaises(ValueError):self.service.handle({'action':'revive','key':key})
