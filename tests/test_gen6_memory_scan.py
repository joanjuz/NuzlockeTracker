"""Safe Gen6 memory discovery: bounded scan, checksum and full 31-box proof."""
import unittest
from tracker.gen6_memory_scan import search_pc_memory, CHUNK
from tracker.boxes import BOX_SIZE
from tracker.profiles import PROFILES
from test_gen6_compat import party_fixture


class FakeMemory:
    def __init__(self,reference,offset=-4096,duplicates=False):
        self.start=reference-0x80000
        self.end=reference+0x80000+31*BOX_SIZE
        self.content=bytearray(self.end-self.start)
        self.base=reference+offset
        self.requests=[]
        body=party_fixture()[128:360]
        start=self.base-self.start
        self.content[start:start+232]=body
        if duplicates:
            self.content[start+232:start+464]=body
    def read(self,address,length):
        if length>CHUNK:raise ValueError('Leer demasiado')
        self.requests.append((address,length))
        pos=address-self.start
        if pos<0 or pos+length>len(self.content):
            raise ValueError('Fuera de la ventana de diagnóstico')
        return bytes(self.content[pos:pos+length])


class Gen6MemoryScanTests(unittest.TestCase):
    def test_locate_single_unknown_offset_and_publish_only_verified_pc(self):
        profile=PROFILES['Pokémon X 1.0']
        memory=FakeMemory(profile.box_address)
        found,boxes,report=search_pc_memory(memory,profile.box_address)
        self.assertEqual(found,memory.base)
        self.assertEqual(len(boxes),31)
        self.assertEqual(boxes['1'][0]['species_id'],25)
        self.assertEqual(len(boxes['31']),30)
        self.assertEqual(report['fully_verified_bases'],[hex(memory.base)])
        self.assertEqual(report['valid_pk6_hits'],1)
        self.assertEqual(report['read_errors'],0)
        self.assertNotIn('nickname',str(report))
        self.assertNotIn('ot_id',str(report))
        self.assertLessEqual(max(length for _,length in memory.requests),65536)

    def test_ambiguous_box_alignment_is_never_accepted(self):
        profile=PROFILES['Pokémon X 1.0']
        memory=FakeMemory(profile.box_address,duplicates=True)
        base,boxes,report=search_pc_memory(memory,profile.box_address)
        self.assertIsNone(base)
        self.assertIsNone(boxes)
        self.assertTrue(report['ambiguous'])

    def test_no_pk6_gives_actionable_summary_without_guess(self):
        profile=PROFILES['Pokémon X 1.0']
        memory=FakeMemory(profile.box_address)
        memory.content[:]=bytes(len(memory.content))
        base,boxes,report=search_pc_memory(memory,profile.box_address)
        self.assertIsNone(base)
        self.assertIsNone(boxes)
        self.assertEqual(report['valid_pk6_hits'],0)
        self.assertEqual(report['candidate_addresses'],[])
