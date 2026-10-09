import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tracker.service import TrackerService
class ServiceTests(unittest.TestCase):
 def setUp(self):
  self.directory=tempfile.TemporaryDirectory();self.path=Path(self.directory.name)/'state.json';self.service=TrackerService(self.path)
 def tearDown(self):self.directory.cleanup()
 def test_unchanged_state_does_not_publish(self):
  self.assertTrue(self.service.update(stale=False));before=self.path.stat().st_mtime_ns
  self.assertFalse(self.service.update(stale=False));self.assertEqual(self.path.stat().st_mtime_ns,before)
  self.assertEqual(json.loads(self.path.read_text())['revision'],1)
 def test_snapshot_is_isolated(self):
  snapshot=self.service.snapshot();snapshot['party'][0]={'wrong':True};self.assertIsNone(self.service.snapshot()['party'][0])
 def test_scan_all_boxes(self):
  self.service.reader=object();self.service.handle({'action':'scan'})
  with patch('tracker.service.capture_party',return_value=b''),patch('tracker.service.decode_party',return_value=[None]*6),patch('tracker.service.read_box',return_value=b''),patch('tracker.service.decode_box',return_value=[None]*30):
   for _ in range(32):self.service.poll()
  state=self.service.snapshot();self.assertEqual(len(state['boxes']),32);self.assertEqual(state['scan'],{'active':False,'completed':32});self.assertIsNone(self.service.scan_next)
 def test_diagnostic_saved_to_disk_without_partner_secrets(self):
  self.service.diagnostic={'error':'No se encontró RAM','pid':5678,
                            'mode':'dynamic','regions_scanned':1050}
  file=Path(self.service.save_diagnostic())
  self.assertTrue(file.is_file())
  self.assertEqual(file.parent,self.path.parent/'diagnosticos')
  data=json.loads(file.read_text(encoding='utf-8'))
  self.assertEqual(data['diagnostic']['regions_scanned'],1050)
  self.assertNotIn('party',str(data))
  self.assertNotIn('companion',str(data))
  self.assertNotIn('token',str(data))
  self.assertNotIn('password',str(data))
  self.assertNotIn('boxes',str(data))
  self.assertTrue(Path(self.service.save_diagnostic()).is_file())

 def test_auto_scan_starts_after_connect(self):
  self.service.factory=lambda config: object()
  self.service.config={'game':'Ultra Moon 1.0','mode':'memory'}
  self.service.connect()
  self.assertEqual(self.service.scan_next,1)
  self.assertEqual(self.service.snapshot()['scan'],{'active':True,'completed':0})
  self.assertGreater(self.service.next_box_refresh_at,0)
 def test_periodic_full_scan_starts_automatically(self):
  self.service.reader=object()
  self.service.next_box_refresh_at=0
  with patch.object(self.service,'poll',side_effect=lambda:self.service.stop.set()) as poll:
   self.service.run()
  poll.assert_called_once()
  self.assertEqual(self.service.scan_next,1)
  self.assertTrue(self.service.snapshot()['scan']['active'])
 def test_manual_death_and_revival_from_routes(self):
  mon={'species_id':448,'nickname':'Lucario','origin_version':33,'encryption_constant':123,
       'met_location_id':8,'checksum_valid':True,'egg':False,'hp':100,'max_hp':100}
  self.service.update(party=[mon]+[None]*5,stale=True)
  key='33:123'
  self.assertEqual(self.service.validate_mark_dead({'key':key})['nickname'],'Lucario')
  self.service.handle({'action':'mark_dead','key':key})
  self.assertIn(key,self.service.snapshot()['progress']['deaths'])
  self.assertEqual(self.service.snapshot()['progress']['deaths'][key]['source'],'manual')
  with self.assertRaisesRegex(ValueError,'ya está registrado'):
   self.service.handle({'action':'mark_dead','key':key})
  self.service.handle({'action':'revive','key':key})
  self.assertNotIn(key,self.service.snapshot()['progress']['deaths'])
  with self.assertRaisesRegex(ValueError,'No se encontró'):
   self.service.handle({'action':'mark_dead','key':'33:99999'})
  self.assertTrue(self.service.snapshot()['progress']['revived_pending'])
  self.service.handle({'action':'mark_dead','key':key})
  self.assertNotIn(key,self.service.snapshot()['progress']['revived_pending'])
 def test_last_party_survives_disconnect_restart_and_template_refresh(self):
  mon={'species_id':37,'species':'Vulpix','form':1,'nickname':'Nevada','hp':24,'max_hp':70,
       'origin_version':33,'encryption_constant':1234,'moves':[0,0,0,0]}
  self.service.update(game='Ultra Moon 1.0',party=[mon]+[None]*5,stale=False)
  self.service.handle({'action':'disconnect'})
  self.assertEqual(self.service.snapshot()['party'][0]['nickname'],'Nevada')
  self.assertTrue(self.service.snapshot()['stale'])
  again=TrackerService(self.path)
  snap=again.snapshot()
  self.assertTrue(snap['stale'])
  self.assertEqual(snap['connection']['status'],'disconnected')
  self.assertEqual(snap['party'][0]['hp'],24)
  self.assertEqual(snap['party'][0]['nickname'],'Nevada')
  self.assertEqual(snap['party'][0]['evolutions'][0]['target_name'],'Ninetales de Alola')
  self.assertEqual(snap['party'][0]['evolutions'][0]['sprite_id'],10104)
  self.assertEqual(snap['party'][0]['evolutions'][0]['method'],'Usar piedra hielo')
  self.service.handle({'action':'disconnect'})
  self.assertEqual(self.service.snapshot()['party'][0]['hp'],24)
  again.factory=lambda config:object()
  again.config={'game':'Ultra Sun 1.0','mode':'memory'}
  again.connect()
  self.assertTrue(all(p is None for p in again.snapshot()['party']))

 def test_cached_boxes_survive_disconnect_and_restart(self):
  mon={'species_id':448,'nickname':'Lucario','origin_version':33,'encryption_constant':123,'checksum_valid':True}
  full={str(n):[mon]+[None]*29 for n in range(1,33)}
  self.service.update(boxes=full,game='Ultra Moon 1.0',stale=False,selected_box=17)
  self.service.handle({'action':'disconnect'})
  self.assertEqual(len(self.service.snapshot()['boxes']),32)
  self.assertTrue(self.service.snapshot()['stale'])
  reboot=TrackerService(self.path)
  self.assertEqual(len(reboot.snapshot()['boxes']),32)
  self.assertEqual(reboot.snapshot()['boxes']['17'][0]['nickname'],'Lucario')
  self.assertEqual(reboot.snapshot()['selected_box'],17)
  self.assertTrue(reboot.snapshot()['stale'])
  self.assertEqual(reboot.snapshot()['connection']['status'],'disconnected')
  reboot.factory=lambda config:object()
  reboot.config={'game':'Ultra Moon 1.0','mode':'memory'}
  reboot.connect()
  self.assertEqual(len(reboot.snapshot()['boxes']),32)
  self.assertTrue(reboot.snapshot()['scan']['active'])
  reboot.config={'game':'Ultra Sun 1.0','mode':'memory'}
  reboot.connect()
  self.assertEqual(reboot.snapshot()['boxes'],{})
 def test_cached_boxes_remain_on_read_error(self):
  mon={'species_id':448,'nickname':'Goty'}
  self.service.update(boxes={str(i):[mon]+[None]*29 for i in range(1,33)})
  self.service.config={'mode':'memory','game':'Ultra Moon 1.0'}
  self.service.reader=object()
  self.service.next_box_refresh_at=99999999999
  with patch.object(self.service,'poll',side_effect=RuntimeError('Lime3DS terminó')):
   with patch.object(self.service.stop,'wait',side_effect=lambda interval: self.service.stop.set()):
    self.service.run()
  self.assertEqual(len(self.service.snapshot()['boxes']),32)
  self.assertEqual(self.service.snapshot()['connection']['status'],'retrying')
  self.assertTrue(self.service.snapshot()['stale'])
 def test_reject_manual_death_for_unverified_or_egg(self):
  self.service.update(party=[{'origin_version':33,'encryption_constant':1,'checksum_valid':False}]+[None]*5)
  with self.assertRaises(ValueError):self.service.validate_mark_dead({'key':'33:1'})
  self.service.update(party=[{'origin_version':33,'encryption_constant':2,'checksum_valid':True,'egg':True}]+[None]*5)
  with self.assertRaises(ValueError):self.service.validate_mark_dead({'key':'33:2'})
 def test_disconnect_stops_retry(self):
  self.service.config={'mode':'memory'};self.service.handle({'action':'disconnect'});self.assertIsNone(self.service.config);self.assertTrue(self.service.snapshot()['stale'])
