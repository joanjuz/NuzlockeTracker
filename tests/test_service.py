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
 def test_disconnect_stops_retry(self):
  self.service.config={'mode':'memory'};self.service.handle({'action':'disconnect'});self.assertIsNone(self.service.config);self.assertTrue(self.service.snapshot()['stale'])
