import unittest
from unittest.mock import patch
from tracker.process_memory import DiscoveryCancelled,DiscoveryLimit
from tracker import process_memory as memory
from tracker.gen6_pc import Gen6BoxProbe
from tracker.gen6_memory_scan import search_pc_memory
from tracker.gen7_pc import Gen7BoxProbe
from tracker.profiles import PROFILES
from tracker.boxes import BOX_BASE
from test_memory_safety import SparseProcess

class MemoryCancellationTests(unittest.TestCase):
 def test_gen6_probe_reader_cancellation_is_not_rejection(self):
  class Reader:
   calls=0
   def read(self,address,length):self.calls+=1;raise DiscoveryCancelled('cancel')
  r=Reader();p=Gen6BoxProbe(PROFILES['Pokémon X 1.0'].box_address)
  with self.assertRaises(DiscoveryCancelled):p.read(r,1)
  self.assertEqual(r.calls,1);self.assertEqual(p.errors,{})
  self.assertEqual(p.last_index,0)
 def test_gen6_search_reader_cancellation_stops_first_read(self):
  class Reader:
   calls=0
   def read(self,address,length):self.calls+=1;raise DiscoveryCancelled('cancel')
  r=Reader()
  with self.assertRaises(DiscoveryCancelled):search_pc_memory(r,PROFILES['Pokémon X 1.0'].box_address)
  self.assertEqual(r.calls,1)
 def test_gen6_search_callback_after_read_blocks_next_read(self):
  class Reader:
   calls=0
   def read(self,address,length):self.calls+=1;return bytes(length)
  r=Reader()
  with self.assertRaises(DiscoveryCancelled):search_pc_memory(r,PROFILES['Pokémon X 1.0'].box_address,cancel=lambda:r.calls>0)
  self.assertEqual(r.calls,1)
 def test_box_callbacks_cancel_during_second_read_without_publication(self):
  for kind,base in ((Gen6BoxProbe,PROFILES['Pokémon X 1.0'].box_address),(Gen7BoxProbe,BOX_BASE)):
   with self.subTest(kind=kind):
    class Reader:
     calls=0
     def read(self,address,length):self.calls+=1;return bytes(length)
    r=Reader();p=kind(base,cancel=lambda:r.calls>=2)
    with self.assertRaises(DiscoveryCancelled):p.read(r,1)
    self.assertEqual(r.calls,2);self.assertEqual(p.boxes[base],{})
 def test_cached_last_read_cancellation_invalidates_cache(self):
  with memory._CACHE_LOCK:memory._DISCOVERY_CACHE.clear()
  p=SparseProcess();memory.discover_dynamic_ram(p);p.calls.clear()
  with self.assertRaises(DiscoveryCancelled):memory.discover_dynamic_ram(p,cancel=lambda:len(p.calls)>=2)
  self.assertEqual(len(p.calls),2)
  self.assertNotIn(memory._cache_key(p,7),memory._DISCOVERY_CACHE)
 def test_read_deadline_checked_after_blocking_read(self):
  p=SparseProcess()
  with patch.object(memory.time,'monotonic',side_effect=[0,0,2]):
   bounded=memory._ReadBudget(p,1,10000,None)
   with self.assertRaises(DiscoveryLimit):bounded.read(p.anchor,2914)
  self.assertEqual(len(p.calls),1)
 def test_gen6_search_cpu_loop_checks_cancel_without_more_reads(self):
  class Reader:
   calls=0
   def read(self,address,length):self.calls+=1;return bytes(length)
  r=Reader();checks=0
  def cancel():
   nonlocal checks
   checks+=1
   return checks>=7
  with self.assertRaises(DiscoveryCancelled):search_pc_memory(r,PROFILES['Pokémon X 1.0'].box_address,cancel=cancel)
  self.assertEqual(r.calls,1)
