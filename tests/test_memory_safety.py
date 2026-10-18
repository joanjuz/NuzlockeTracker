import struct
import unittest
from unittest.mock import patch
from tracker import process_memory as memory
from tracker.gen7_pc import Gen7BoxProbe
from tracker.pokemon import crypt
from tracker.boxes import BOX_BASE,BOX_SIZE
from test_process_memory import party_data


class SparseProcess:
    def __init__(self,guest=memory.PARTY-128,identity='first',generation=7):
        self.base=0x100000040;self.guest=guest;self.generation=generation
        self.pid=42;self.name='lime3ds.exe';self.calls=[];self.blocks={}
        self.metadata={'pid':42,'creation_id':identity}
        raw=bytearray(party_data());struct.pack_into('<III',raw,68,guest+128,guest+472,guest+408)
        self.anchor=self.base+guest-(0x08000000 if generation==6 else memory.LINEAR)
        self.blocks[self.anchor]=bytes(raw);self.ranges=[(self.base-64,256*1024**2)]
    def regions(self):return self.ranges
    def read(self,address,length):
        self.calls.append((address,length));out=bytearray(length)
        for start,raw in self.blocks.items():
            lo=max(address,start);hi=min(address+length,start+len(raw))
            if hi>lo:out[lo-address:hi-address]=raw[lo-start:hi-start]
        return bytes(out)
    def alive(self):return True
    def close(self):pass


class DetectionSafetyTests(unittest.TestCase):
    def setUp(self):
        with memory._CACHE_LOCK:memory._DISCOVERY_CACHE.clear()

    def test_quick_probe_finds_moon_minus128_and_repeats_checksum_validation(self):
        p=SparseProcess()
        with patch.object(memory,'_scan_dynamic_ram',side_effect=AssertionError('slow scan')):
            self.assertEqual(memory.discover_dynamic_ram(p),(0x100000040,memory.PARTY-128))
        self.assertEqual(p.discovery_report['source'],'region_probe')
        self.assertGreaterEqual(p.calls.count((p.anchor,2914)),2)
        self.assertLess(p.discovery_report['bytes_scanned'],2*1024**2)

    def test_gen6_retains_independent_known_party_candidates(self):
        from tracker.profiles import POKEMON_X_10
        p=SparseProcess(POKEMON_X_10.party_address,generation=6)
        self.assertEqual(memory.discover_dynamic_ram(p,generation=6),(p.base,0x08CE1CE8))
        self.assertEqual(p.discovery_report['source'],'region_probe')

    def test_unknown_layout_uses_real_slow_fallback(self):
        p=SparseProcess(memory.PARTY+0x2400)
        p.ranges=[(p.anchor-100,4096)]
        self.assertEqual(memory.discover_dynamic_ram(p),(p.base,p.guest))
        self.assertEqual(p.discovery_report['source'],'dynamic_scan')

    def test_dynamic_scan_rejects_distinct_copies_even_with_different_party_sizes(self):
        p=SparseProcess(memory.PARTY+0x2400)
        other=p.anchor+8192;p.blocks[other]=p.blocks[p.anchor]
        p.ranges=[(p.anchor-100,16384)]
        with self.assertRaisesRegex(memory.DiscoveryError,'Varias copias'):
            memory.discover_dynamic_ram(p)

    def test_probe_rejects_ambiguous_regions(self):
        p=SparseProcess();other=p.base+0x20000000
        p.ranges.append((other-64,256*1024**2))
        p.blocks[other+p.guest-memory.LINEAR]=p.blocks[p.anchor]
        with self.assertRaisesRegex(memory.DiscoveryError,'Varias copias'):
            memory.discover_dynamic_ram(p)
        self.assertEqual(len(memory._DISCOVERY_CACHE),0)

    def test_torn_quick_probe_does_not_publish_candidate(self):
        p=SparseProcess();original=p.read;reads=0
        def read(address,length):
            nonlocal reads
            raw=original(address,length)
            if address==p.anchor:
                reads+=1
                if reads>1:return bytes(length)
            return raw
        p.read=read
        with self.assertRaises(memory.DiscoveryError):
            memory.discover_dynamic_ram(p,budget=1024**2)
        self.assertEqual(len(memory._DISCOVERY_CACHE),0)

    def test_checksum_failure_is_rejected_before_fallback(self):
        p=SparseProcess();bad=bytearray(p.blocks[p.anchor]);bad[144]^=1;p.blocks[p.anchor]=bytes(bad)
        found,report=memory.probe_region_ram(p)
        self.assertIsNone(found);self.assertEqual(report['valid_candidates'],0)

    def test_cache_revalidates_same_instance_without_rescanning(self):
        p=SparseProcess();first=memory.discover_dynamic_ram(p)
        p.calls.clear()
        with patch.object(memory,'probe_region_ram',side_effect=AssertionError('probe')):
            self.assertEqual(memory.discover_dynamic_ram(p),first)
        self.assertEqual(p.discovery_report['source'],'cache')
        self.assertEqual(p.calls,[(p.anchor,2914),(p.anchor,2914)])

    def test_pid_reuse_and_generation_change_never_reuse_cached_address(self):
        p=SparseProcess();memory.discover_dynamic_ram(p)
        replacement=SparseProcess(identity='replacement')
        with patch.object(memory,'probe_region_ram',wraps=memory.probe_region_ram) as probe:
            memory.discover_dynamic_ram(replacement)
        probe.assert_called_once()
        self.assertNotIn((42,'first',7),memory._DISCOVERY_CACHE)
        from tracker.profiles import POKEMON_X_10
        gen6=SparseProcess(POKEMON_X_10.party_address,identity='replacement',generation=6)
        with patch.object(memory,'probe_region_ram',wraps=memory.probe_region_ram) as probe:
            memory.discover_dynamic_ram(gen6,generation=6)
        probe.assert_called_once()
        self.assertEqual(gen6.discovery_report['source'],'region_probe')

    def test_stale_cached_wrapper_is_invalidated_before_new_probe(self):
        p=SparseProcess();memory.discover_dynamic_ram(p)
        p.blocks[p.anchor]=bytes(2914)
        with patch.object(memory,'probe_region_ram',return_value=(None,{})), \
             patch.object(memory,'_scan_dynamic_ram',side_effect=memory.DiscoveryError('not found')):
            with self.assertRaisesRegex(memory.DiscoveryError,'not found'):memory.discover_dynamic_ram(p)
        self.assertEqual(len(memory._DISCOVERY_CACHE),0)

    def test_missing_creation_identity_disables_cache(self):
        p=SparseProcess(identity=None);memory.discover_dynamic_ram(p)
        self.assertEqual(len(memory._DISCOVERY_CACHE),0)

    def test_byte_budget_includes_probe_reads_and_does_not_overrun(self):
        p=SparseProcess()
        with self.assertRaisesRegex(memory.DiscoveryError,'límite de lectura') as caught:
            memory.discover_dynamic_ram(p,budget=2914)
        self.assertEqual(caught.exception.diagnostic['bytes_scanned'],2914)
        self.assertEqual(len(p.calls),1)

    def test_cancellation_interrupts_probe_without_swallowing(self):
        p=SparseProcess()
        with self.assertRaises(memory.DiscoveryCancelled):
            memory.discover_dynamic_ram(p,cancel=lambda:len(p.calls)>=1)
        self.assertEqual(len(p.calls),1)

    def test_deadline_applies_before_probe_and_cache(self):
        p=SparseProcess()
        with patch.object(memory.time,'monotonic',side_effect=[0,2,2]):
            with self.assertRaisesRegex(memory.DiscoveryError,'límite de tiempo'):
                memory.discover_dynamic_ram(p,timeout=1)
        self.assertEqual(p.calls,[])

    def test_title_hints_distinguish_games_and_do_not_use_origin_version(self):
        for title,expected in [('Lime3DS | Pokémon Ultra Moon','Ultra Moon 1.0'),
                               ('Pokémon Ultra Sol','Ultra Sun 1.0'),('Pokémon Y','Pokémon Y 1.0'),
                               ('Citra | settings',None)]:
            with self.subTest(title=title):self.assertEqual(memory.game_hint_from_title(title),expected)


class Gen7PcTests(unittest.TestCase):
    def populated(self):return party_data()[128:360]+bytes(BOX_SIZE-232)
    def reader(self,blocks=None):
        class Reader:
            def __init__(self):self.calls=[]
            def read(self,address,length):
                self.calls.append((address,length));return (blocks or {}).get(address,bytes(length))
        return Reader()
    def scan(self,probe,reader):
        for n in range(1,33):probe.read(reader,n)
        return probe.finish()

    def test_complete_double_pc_verifies_unshifted_moon_address(self):
        reader=self.reader({BOX_BASE:self.populated()});probe=Gen7BoxProbe((BOX_BASE,BOX_BASE-128))
        base,boxes=self.scan(probe,reader)
        self.assertEqual(base,BOX_BASE);self.assertEqual(len(boxes),32)
        self.assertEqual(boxes['1'][0]['species_id'],637)
        self.assertEqual(probe.status,'verified')
        self.assertEqual(reader.calls.count((BOX_BASE+31*BOX_SIZE,BOX_SIZE)),2)
        count=len(reader.calls);probe.read(reader,1);probe.read(reader,32);self.assertEqual(probe.finish()[0],BOX_BASE)
        self.assertEqual(len(reader.calls),count)

    def test_all_empty_boxes_remain_pending_not_verified(self):
        probe=Gen7BoxProbe();reader=self.reader()
        self.assertEqual(self.scan(probe,reader),(None,None));self.assertEqual(probe.status,'pending_empty')
        self.assertEqual(len(reader.calls),64)

    def test_corrupt_last_box_prevents_partial_publication(self):
        reader=self.reader({BOX_BASE:self.populated(),BOX_BASE+31*BOX_SIZE:b'bad'+bytes(BOX_SIZE-3)})
        probe=Gen7BoxProbe();self.assertEqual(self.scan(probe,reader),(None,None))
        self.assertEqual(probe.status,'invalid')
        self.assertEqual(probe.diagnostic()['candidates'][0]['first_rejection']['box'],32)

    def test_two_populated_candidates_are_ambiguous(self):
        other=BOX_BASE+0x100000;reader=self.reader({BOX_BASE:self.populated(),other:self.populated()})
        probe=Gen7BoxProbe((BOX_BASE,other));self.assertEqual(self.scan(probe,reader),(None,None))
        self.assertEqual(probe.status,'ambiguous')

    def test_torn_box_and_cancellation_reject_publication(self):
        reader=self.reader({BOX_BASE:self.populated()});original=reader.read
        def torn(address,length):
            raw=original(address,length)
            return bytes(length) if len(reader.calls)==2 else raw
        reader.read=torn;probe=Gen7BoxProbe();self.assertEqual(self.scan(probe,reader),(None,None))
        self.assertEqual(probe.status,'invalid')
        reader=self.reader();probe=Gen7BoxProbe(cancel=lambda:len(reader.calls)>0)
        with self.assertRaises(memory.DiscoveryCancelled):probe.read(reader,1)
        self.assertEqual(probe.last_index,0)

    def test_out_of_order_invalid_address_and_incomplete_scan_are_rejected(self):
        for address in (0,0x40000000,True):
            with self.subTest(address=address),self.assertRaises(ValueError):Gen7BoxProbe(address)
        probe=Gen7BoxProbe()
        with self.assertRaises(ValueError):probe.read(self.reader(),2)
        with self.assertRaises(ValueError):probe.finish()


if __name__=='__main__':unittest.main()
