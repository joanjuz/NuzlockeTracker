import tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from tracker.demo import DemoService
class DemoTests(unittest.TestCase):
 def setUp(self):
  self.directory=tempfile.TemporaryDirectory();self.demo=DemoService(Path(self.directory.name)/'demo.json')
 def tearDown(self):self.directory.cleanup()
 def test_scenarios_and_reset(self):
  self.assertTrue(self.demo.snapshot()['demo']);self.assertEqual(len(self.demo.snapshot()['party']),6)
  self.demo.scenario('damage');self.assertEqual(self.demo.snapshot()['party'][0]['hp'],0)
  self.demo.scenario('empty');self.assertEqual(self.demo.snapshot()['party'],[None]*6)
  self.demo.scenario('stale');self.assertTrue(self.demo.snapshot()['stale'])
  self.demo.scenario('normal');self.assertFalse(self.demo.snapshot()['stale']);self.assertEqual(self.demo.snapshot()['party'][0]['hp'],304)
 def test_box_data_is_independent_and_has_no_combat_stats(self):
  self.assertEqual(self.demo.box_data(4),[None]*30)
  data=self.demo.box_data(1);self.assertIsNone(data[0]['level']);self.assertIsNone(data[0]['stats'])
  data[0]['nickname']='alterado';self.assertEqual(self.demo.team[0]['nickname'],'Botella')
 def test_worker_never_opens_emulator(self):
  with patch('tracker.service.LimeProcessMemory',side_effect=AssertionError('Memoria prohibida')),patch('tracker.service.LimeGDB',side_effect=AssertionError('GDB prohibido')):
   worker=threading.Thread(target=self.demo.run);worker.start()
   try:
    self.demo.commands.put({'action':'connect','mode':'memory'});self.demo.commands.put({'action':'scan'})
    deadline=time.monotonic()+2
    while len(self.demo.snapshot()['boxes'])<3 and time.monotonic()<deadline:time.sleep(.02)
    self.assertGreaterEqual(len(self.demo.snapshot()['boxes']),3);self.assertIsNone(self.demo.reader)
   finally:self.demo.stop.set();worker.join(2)
