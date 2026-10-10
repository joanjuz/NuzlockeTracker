import unittest
from tracker.gen6_diagnostic import find_deposited_box
from tracker.profiles import PROFILES
from tracker.boxes import BOX_SIZE
from test_gen6_compat import party_fixture

class Memory:
    def __init__(self,filled=True):
        self.start=0x08000000
        self.data=bytearray(0x100000)
        self.base=self.start+0x50000
        self.pk=party_fixture()[128:360]
        if filled:
            off=self.base-self.start
            self.data[off:off+232]=self.pk
    def read(self,address,length):
        offset=address-self.start
        if offset<0 or offset+length>len(self.data):
            raise ValueError('Fuera de RAM')
        return bytes(self.data[offset:offset+length])

class Gen6DepositDiagnosticTests(unittest.TestCase):
    def test_find_box_from_known_party_pokemon_and_full_scan(self):
        reader=Memory()
        result=find_deposited_box(reader,0x1234,25,start=reader.start,end=reader.start+len(reader.data))
        self.assertEqual(result['complete_box_base'],hex(reader.base))
        self.assertEqual(result['valid_stored_pk6_addresses'],[hex(reader.base)])
        self.assertEqual(result['ec_match_count'],1)
        self.assertFalse(result['ambiguous'])
        self.assertNotIn('nickname',str(result))
        self.assertNotIn('ot_id',str(result))

    def test_does_not_invent_pc_when_ec_absent_or_wrong_species(self):
        for filled,ec,sp in [(False,0x1234,25),(True,0x5678,25),(True,0x1234,37)]:
            with self.subTest(filled=filled,ec=ec,sp=sp):
                r=Memory(filled)
                result=find_deposited_box(r,ec,sp,start=r.start,end=r.start+len(r.data))
                self.assertIsNone(result['complete_box_base'])

    def test_known_ec_in_unrelated_stored_pk6_not_a_full_pc(self):
        r=Memory()
        # Second copy appears far from Box1 and cannot validate all 31 boxes.
        r.data[0x20000:0x20000+232]=r.pk
        out=find_deposited_box(r,0x1234,25,start=r.start,end=r.start+len(r.data))
        self.assertEqual(out['complete_box_base'],hex(r.base))
        self.assertEqual(len(out['valid_stored_pk6_addresses']),2)

    def test_invalid_ranges_refused(self):
        r=Memory()
        with self.assertRaises(ValueError):
            find_deposited_box(r,0,25,start=r.start,end=r.start+0x10000)
        with self.assertRaises(ValueError):
            find_deposited_box(r,0x1234,722,start=r.start,end=r.start+0x10000)
