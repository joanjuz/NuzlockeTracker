import struct
import unittest
from tracker.pokemon import decode_slot, crypt, PERMUTATIONS
from tracker.profiles import capture_party
class DecodeTests(unittest.TestCase):
    def test_every_block_order(self):
        for n in range(24):
            seed=n<<13; data=bytearray(232)
            struct.pack_into('<I',data,0,seed); struct.pack_into('<H',data,8,637)
            data[0x62:0x66]=bytes([3,5,7,9]);data[0x66:0x6A]=bytes([0,1,2,3]);data[28]=11; data[64:76]='Botell'.encode('utf-16le')
            struct.pack_into('<H',data,6,sum(struct.unpack('<112H',data[8:]))&65535)
            shuffled=b''.join(data[8+k*56:8+(k+1)*56] for k in PERMUTATIONS[n])
            snapshot=bytearray(494); snapshot[128:360]=data[:8]+crypt(shuffled,seed)
            stats=bytearray(22); stats[4]=100; struct.pack_into('<7H',stats,8,10,304,211,153,249,317,224)
            snapshot[472:494]=crypt(stats,seed)
            p=decode_slot(snapshot,0)
            self.assertEqual(p['move_pp'],[3,5,7,9]);self.assertEqual(p['move_pp_ups'],[0,1,2,3])
            self.assertEqual((p['species_id'],p['hp'],p['stats']['ATE']),(637,10,317))
            snapshot[140]^=1
            with self.assertRaises(ValueError): decode_slot(snapshot,0)
    def test_capture_includes_last_stats(self):
        class Reader:
            def read(self,address,length): self.length=length; return bytes(length)
        reader=Reader(); self.assertEqual(len(capture_party(reader)),2914)
    def test_short_data(self):
        with self.assertRaises(ValueError): decode_slot(bytes(200),0)


def _encoded_slot(*, species=25, tid=0, sid=0, pid=0, byte_1d=0, seed=0x1234):
    """Encrypted PK6/PK7 party slot (same layout for both generations)."""
    data=bytearray(232)
    struct.pack_into('<I',data,0,seed)
    struct.pack_into('<H',data,8,species)
    struct.pack_into('<HH',data,0x0C,tid,sid)
    struct.pack_into('<I',data,0x18,pid)
    data[0x1D]=byte_1d
    struct.pack_into('<H',data,6,sum(struct.unpack('<112H',data[8:]))&0xffff)
    order=PERMUTATIONS[((seed>>13)&31)%24]
    shuffled=b''.join(data[8+k*56:8+(k+1)*56] for k in order)
    snapshot=bytearray(494);snapshot[128:360]=data[:8]+crypt(shuffled,seed)
    stats=bytearray(22);stats[4]=50;struct.pack_into('<7H',stats,8,90,100,50,50,50,50,50)
    snapshot[472:494]=crypt(stats,seed)
    return bytes(snapshot)


class GenderAndShinyTests(unittest.TestCase):
    """PKHeX PK6/PK7: Gender=(Data[0x1D]>>1)&3, Form=Data[0x1D]>>3,
    TID16/SID16 at 0x0C/0x0E, PID at 0x18 and the Gen6+ shiny threshold 16."""

    def test_gender_bits_do_not_alter_form(self):
        for gender in (0,1,2):
            for max_species in (721,807):
                with self.subTest(gender=gender,max_species=max_species):
                    # Bit 0 is the fateful-encounter flag; form 3 lives in bits 3-7.
                    p=decode_slot(_encoded_slot(byte_1d=(3<<3)|(gender<<1)|1),0,max_species=max_species)
                    self.assertEqual(p['gender'],gender)
                    self.assertEqual(p['form'],3)

    def test_shiny_uses_gen6_plus_threshold(self):
        tid,sid=0x1234,0x5678
        high=tid^sid
        cases={0:True,15:True,16:False,0xFFFF:False}
        for xor,expected in cases.items():
            with self.subTest(xor=xor):
                pid=(high<<16)|xor
                p=decode_slot(_encoded_slot(tid=tid,sid=sid,pid=pid),0)
                self.assertIs(p['shiny'],expected)
                self.assertEqual(p['ot_id'],tid|(sid<<16))

    def test_shiny_with_shuffled_blocks(self):
        # Seed selecting a non-identity block order still decodes PID/TID.
        p=decode_slot(_encoded_slot(tid=1,sid=2,pid=(3<<16)|0,seed=7<<13),0)
        self.assertTrue(p['shiny'])

    def test_box_slots_also_expose_gender_and_shiny(self):
        from tracker.boxes import decode_box,BOX_SIZE
        slot=_encoded_slot(tid=9,sid=9,pid=0,byte_1d=2<<1)[128:360]
        members=decode_box(slot+bytes(BOX_SIZE-232),max_species=721)
        self.assertEqual((members[0]['gender'],members[0]['shiny']),(2,True))
