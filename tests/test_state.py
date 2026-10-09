import unittest
from tracker.state import SnapshotStore
class StateTests(unittest.TestCase):
 def test_unchanged(self):
  s=SnapshotStore();self.assertTrue(s.update('party',[{'hp':30}]))
  self.assertFalse(s.update('party',[{'hp':30}]))
  self.assertTrue(s.update('party',[{'hp':29}]))
 def test_mutation_does_not_corrupt_previous_snapshot(self):
  s=SnapshotStore();p={'hp':30};s.update('p',p);p['hp']=29
  self.assertTrue(s.update('p',p))
