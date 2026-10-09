import unittest
from tracker.boxes import read_box,decode_box,BOX_BASE,BOX_SIZE
class BoxTests(unittest.TestCase):
 def test_empty(self):self.assertEqual(decode_box(bytes(BOX_SIZE)),[None]*30)
 def test_bad_length(self):
  with self.assertRaises(ValueError):decode_box(bytes(BOX_SIZE-1))
 def test_corrupt_slot(self):
  data=bytearray(BOX_SIZE);data[4]=1
  with self.assertRaisesRegex(ValueError,'slot 1'):decode_box(data)
 def test_addresses_and_bounds(self):
  class Reader:
   def read(self,address,length):self.request=(address,length);return bytes(length)
  r=Reader();read_box(r,32);self.assertEqual(r.request,(BOX_BASE+31*6960,6960))
  for n in [0,33,-1,True]:
   with self.assertRaises(ValueError):read_box(r,n)
