"""Gen6: auto-scan 31 boxes every three minutes and trade detection only after proof."""
import copy,time,tempfile,unittest
from pathlib import Path
from tracker.service import TrackerService
from tracker.progress import RunProgress,pokemon_key
from tracker.profiles import PROFILES
from test_gen6_boxes import Gen6Memory
from test_gen6_compat import party_fixture
from tracker.pokemon import decode_party

class Gen6Autoscans(unittest.TestCase):
 def test_autoscan_starts_after_team_connection_and_schedules_next_refresh(self):
  for game in ('Pokémon X 1.0','Pokémon Y 1.0','Omega Ruby 1.0','Alpha Sapphire 1.0'):
   with self.subTest(game=game),tempfile.TemporaryDirectory() as folder:
    profile=PROFILES[game];reader=Gen6Memory(profile)
    service=TrackerService(Path(folder)/'state.json')
    service.factory=lambda cfg:reader
    service.config={'game':game,'mode':'memory'}
    before=time.monotonic()
    service.connect()
    self.assertEqual(service.scan_next,1)
    self.assertTrue(service.snapshot()['scan']['active'])
    self.assertGreaterEqual(service.next_box_refresh_at,before+179)
    for _ in range(31):service.poll()
    state=service.snapshot()
    self.assertTrue(state['box_verified'])
    self.assertEqual(state['scan'],{'active':False,'completed':31})
    self.assertEqual(len(state['boxes']),31)
    self.assertIsNone(service.scan_next)
    self.assertGreaterEqual(service.next_box_refresh_at,before+179)
    self.assertEqual(service.scan_verified,set(range(1,32)))
    self.assertTrue(service.progress.data['full_scan_baseline'])

 def test_gen6_complete_box_trade_auto_classification_but_partial_must_not(self):
  with tempfile.TemporaryDirectory() as folder:
   run=RunProgress(Path(folder)/'x-progress.json')
   base=decode_party(party_fixture(game_version=24),max_species=721)[0]
   def member(ec,ot):
    p=copy.deepcopy(base)
    p.update(encryption_constant=ec,ot_id=ot,checksum_valid=True)
    return p
   ours=[member(501,12345),member(502,12345),member(503,12345)]
   inbound=member(504,99999)
   boxes={str(i):[None]*30 for i in range(1,32)}
   first=ours+[None]*3
   second=[ours[1],ours[2],inbound,None,None,None]
   run.remember(first,boxes)
   self.assertFalse(run.observe_full_scan(first,boxes,box_count=31))
   run.remember(second,boxes)
   self.assertFalse(run.observe_full_scan(second,{'1':[None]*30},box_count=31))
   self.assertNotIn(pokemon_key(ours[0]),run.data['route_marks'])
   self.assertTrue(run.observe_full_scan(second,boxes,box_count=31))
   self.assertEqual(run.data['route_marks'][pokemon_key(ours[0])]['kind'],'trade')
   self.assertEqual(run.data['origins'][pokemon_key(inbound)],'trade')
   self.assertFalse(run.observe_full_scan(second,boxes,box_count=31))
   # A 31-box snapshot may not pretend to be a 32-box USUM scan.
   usum=RunProgress(Path(folder)/'usum-progress.json')
   self.assertFalse(usum.observe_full_scan(first,boxes,box_count=32))
   self.assertEqual(usum.data['full_scan_baseline'],{})
