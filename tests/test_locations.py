import struct,unittest
from tracker.locations import location_name
from tracker.pokemon import decode_slot,crypt,PERMUTATIONS
class LocationTests(unittest.TestCase):
 def test_names_and_subarea(self):
  self.assertEqual(location_name(8),'Ruta 1')
  self.assertEqual(location_name(6),'Ruta 1 · Afueras de Hauoli')
  self.assertEqual(location_name(40002),'Lugar lejano')
  self.assertEqual(location_name(60002),'Cuidados Pokémon')
 def test_unknown_and_other_origin(self):
  self.assertEqual(location_name(0),'Sin lugar registrado')
  self.assertEqual(location_name(9999),'Lugar ID 9999')
  self.assertIn('juego de origen 24',location_name(8,24))
 def snapshot(self,month=10):
  raw=bytearray(232);seed=7<<13;struct.pack_into('<I',raw,0,seed);struct.pack_into('<H',raw,8,637)
  raw[0xD4:0xD7]=bytes([26,month,8]);struct.pack_into('<HH',raw,0xD8,60002,6);raw[0xDD]=128|5;raw[0xDF]=33
  struct.pack_into('<H',raw,6,sum(struct.unpack('<112H',raw[8:]))&65535)
  shuffled=b''.join(raw[8+k*56:8+(k+1)*56] for k in PERMUTATIONS[7])
  return bytes(128)+raw[:8]+crypt(shuffled,seed)
 def test_decode_encounter_fields_with_shuffled_blocks(self):
  p=decode_slot(self.snapshot(),0)
  self.assertEqual((p['met_location_id'],p['egg_location_id'],p['met_level'],p['origin_version'],p['met_date']),(6,60002,5,33,'2026-10-08'))
 def test_invalid_date_is_not_invented(self):self.assertIsNone(decode_slot(self.snapshot(0),0)['met_date'])
