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
