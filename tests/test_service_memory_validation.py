import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack
from tracker.service import TrackerService
from tracker.boxes import BOX_BASE,BOX_SIZE
from test_memory_safety import party_data

class ServiceMemoryValidationTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.service=TrackerService(Path(self.folder.name)/'state.json')
 def scan(self,blocks):
  class Reader:
   def read(self,address,length):return blocks.get(address,bytes(length))
  self.service.reader=Reader();self.service.handle({'action':'scan'})
  with ExitStack() as stack:
   stack.enter_context(patch('tracker.service.capture_party',return_value=b''))
   stack.enter_context(patch('tracker.service.decode_party',return_value=[None]*6))
   stack.enter_context(patch('tracker.service.apply_battle_hp',return_value=([None]*6,False)))
   stack.enter_context(patch.object(self.service,'enrich',side_effect=lambda p:p))
   for _ in range(31):self.service.poll()
   self.assertFalse(self.service.snapshot()['box_verified'])
   self.service.poll()
  return self.service.snapshot()
 def test_full_verified_pc_published_atomically(self):
  mon=party_data()[128:360]+bytes(BOX_SIZE-232)
  state=self.scan({BOX_BASE:mon})
  self.assertEqual(len(state['boxes']),32)
  self.assertEqual(state['boxes']['1'][0]['species_id'],637)
  self.assertEqual(state['box_status'],'verified');self.assertTrue(state['box_verified'])
 def test_empty_scan_keeps_last_boxes_and_does_not_observe_absence(self):
  old={'1':[{'species_id':25}]+[None]*29}
  self.service.update(boxes=old)
  with patch.object(self.service.progress,'observe_full_scan') as observe:
   state=self.scan({})
  self.assertEqual(state['boxes'],old)
  self.assertEqual(state['box_status'],'pending_empty');observe.assert_not_called()
 def test_corrupt_final_box_rejects_other_valid_boxes(self):
  mon=party_data()[128:360]+bytes(BOX_SIZE-232)
  state=self.scan({BOX_BASE:mon,BOX_BASE+31*BOX_SIZE:b'bad'+bytes(BOX_SIZE-3)})
  self.assertEqual(state['boxes'],{});self.assertEqual(state['box_status'],'invalid')
 def test_known_wrong_title_rejected_before_connector(self):
  self.service.config={'game':'Ultra Moon 1.0','mode':'memory','pid':42}
  with patch('tracker.service.list_emulator_instances',return_value=[{'pid':42,'game_hint':'Ultra Sun 1.0'}]),patch('tracker.service.LimeProcessMemory') as connect:
   with self.assertRaisesRegex(ValueError,'corresponde'):self.service.connect()
  connect.assert_not_called();self.assertIsNone(self.service.reader)
 def test_pid_reuse_rejected_before_connector(self):
  self.service.config={'game':'Ultra Moon 1.0','mode':'memory','pid':42,'creation_id':'100'}
  with patch('tracker.service.list_emulator_instances',return_value=[{'pid':42,'game_hint':None,'creation_id':'101'}]),patch('tracker.service.LimeProcessMemory') as connect:
   with self.assertRaisesRegex(ValueError,'cambió'):self.service.connect()
  connect.assert_not_called()
 def test_unknown_title_allowed_and_identity_persisted(self):
  metadata={'pid':42,'creation_id':'123','game_hint':None}
  self.service.config={'game':'Ultra Moon 1.0','mode':'memory'}
  self.service.factory=lambda cfg:SimpleNamespace(process=SimpleNamespace(metadata=metadata))
  self.service.connect()
  again=TrackerService(self.service.output)
  self.assertEqual(again.config['pid'],42);self.assertEqual(again.config['creation_id'],'123')
  self.assertFalse(again.snapshot()['box_verified'])
 def test_identity_changes_between_enumeration_and_open_are_rejected(self):
  reader=SimpleNamespace(process=SimpleNamespace(metadata={'pid':42,'creation_id':'999','game_hint':None}),close=lambda:None)
  self.service.config={'game':'Ultra Moon 1.0','mode':'memory','pid':42,'creation_id':'123'}
  self.service.factory=lambda cfg:reader
  with self.assertRaisesRegex(ValueError,'cambió'):self.service.connect()
  self.assertIsNone(self.service.reader)
 def test_invalid_identity_cannot_enter_saved_configuration(self):
  config={'game':'Ultra Moon 1.0','mode':'memory','creation_id':'../bad'}
  with self.assertRaises(ValueError):self.service.valid_connection(config)

class ServiceRelocatedPcTests(unittest.TestCase):
 setUp=ServiceMemoryValidationTests.setUp
 scan=ServiceMemoryValidationTests.scan
 def test_unknown_party_guest_keeps_valid_pc_candidate(self):
  from dataclasses import replace
  self.service.profile=replace(self.service.profile,party_address=0x30100000)
  mon=party_data()[128:360]+bytes(BOX_SIZE-232)
  state=self.scan({BOX_BASE:mon})
  self.assertTrue(state['box_verified']);self.assertEqual(len(state['boxes']),32)
 def test_selected_box_cancellation_is_propagated(self):
  from tracker.process_memory import DiscoveryCancelled
  self.service.update(box_verified=True,box_status='verified')
  self.service.sun_box_base=BOX_BASE;self.service.reader=object()
  with patch('tracker.service.capture_party',return_value=b''),patch('tracker.service.decode_party',return_value=[None]*6),patch('tracker.service.apply_battle_hp',return_value=([None]*6,False)),patch('tracker.service.read_box',side_effect=DiscoveryCancelled('cancel')):
   with self.assertRaises(DiscoveryCancelled):self.service.poll()

class LegacyGen6ProbeSafetyTests(unittest.TestCase):
 def test_second_candidate_is_rejected_even_with_fewer_members(self):
  from tracker.process_memory import probe_gen6_region_ram
  class Process:
   def regions(self):return [(0x100000000,256*1024**2)]
   def read(self,address,length):
    import struct
    if address not in (0x100000000+0x08CE1CE8-0x08000000,
                       0x100000020+0x08CE1CE8-0x08000000):return bytes(length)
    data=bytearray(length);struct.pack_into('<I',data,68,0x08CE1CE8+128)
    return bytes(data)
  with patch('tracker.process_memory.decode_party',side_effect=[[{'species_id':1},{'species_id':2}], [{'species_id':1}]]):
   found,report=probe_gen6_region_ram(Process())
  self.assertIsNone(found);self.assertTrue(report['ambiguous'])
 def test_cancelled_read_is_not_swallowed(self):
  from tracker.process_memory import probe_gen6_region_ram,DiscoveryCancelled
  class Process:
   def regions(self):return [(0x100000000,256*1024**2)]
   def read(self,address,length):raise DiscoveryCancelled('cancel')
  with self.assertRaises(DiscoveryCancelled):probe_gen6_region_ram(Process())
