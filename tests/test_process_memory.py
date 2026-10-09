import struct,unittest
from unittest.mock import patch
from tracker.process_memory import NEEDLE,PARTY,LINEAR,BOX_BASE,BOX_SIZE,validate_anchor,LimeProcessMemory,DiscoveryError,discover_ram,supported_emulator
from tracker.pokemon import crypt

def party_data():
 raw=bytearray(2914);raw[68:80]=NEEDLE
 pk=bytearray(232);struct.pack_into('<I',pk,0,0x1234);struct.pack_into('<H',pk,8,637)
 struct.pack_into('<H',pk,6,sum(struct.unpack('<112H',pk[8:]))&65535)
 raw[128:360]=pk[:8]+crypt(pk[8:],0x1234)
 tail=bytearray(22);tail[4]=100;struct.pack_into('<7H',tail,8,50,100,10,20,30,40,50)
 raw[472:494]=crypt(tail,0x1234);return bytes(raw)
class FakeProcess:
 def __init__(self):self.base=0x100000000;self.party=party_data();self.closed=False
 def read(self,address,length):
  anchor=self.base+PARTY-LINEAR;box=self.base+BOX_BASE-LINEAR
  if anchor<=address and address+length<=anchor+len(self.party):return self.party[address-anchor:address-anchor+length]
  if box<=address and address+length<=box+BOX_SIZE:return bytes(length)
  return bytes(length)
 def alive(self):return not self.closed
 def close(self):self.closed=True
class ProcessMemoryTests(unittest.TestCase):
 def test_process_names_lime_citra_azahar(self):
  for name in ('lime3ds.exe','Lime3DS-Qt.exe','citra-qt.exe','Citra.exe','Azahar.exe','azahar-qt.exe'):
   self.assertTrue(supported_emulator(name),name)
  for name in ('lime3ds.dat','python.exe','citra-helper.dll','not-azahar.exe','azahar.exe.exe.bat'):
   self.assertFalse(supported_emulator(name),name)

 def test_anchor_translation(self):
  p=FakeProcess();self.assertEqual(validate_anchor(p,p.base+PARTY-LINEAR),p.base)
 def test_invalid_signature(self):
  p=FakeProcess();p.party=bytes(2914)
  with self.assertRaises(DiscoveryError):validate_anchor(p,p.base+PARTY-LINEAR)
 def connector(self):
  c=LimeProcessMemory.__new__(LimeProcessMemory);c.process=FakeProcess();c.base=c.process.base;return c
 def test_read_matches_guest_bytes(self):
  c=self.connector();self.assertEqual(c.read(PARTY,2914),c.process.party);self.assertEqual(c.read(BOX_BASE,BOX_SIZE),bytes(BOX_SIZE))
 def test_restart_signature(self):
  c=self.connector();c.process.party=bytes(2914)
  with self.assertRaisesRegex(DiscoveryError,'reiniciada'):c.read(PARTY,1)
 def test_closed_process(self):
  c=self.connector();c.process.closed=True
  with self.assertRaisesRegex(DiscoveryError,'cerró'):c.read(PARTY,1)
 def test_bounds(self):
  c=self.connector()
  for addr,length in [(0,1),(PARTY,0),(PARTY,65537),(0x3fffffff,2)]:
   with self.assertRaises(ValueError):c.read(addr,length)
 def test_discovery_boundary_pattern(self):
  class Process:
   def regions(self):return [(0x100000000,64*1024**2)]
   def read(self,address,length):
    start=0x100000000+4*1024**2-2;data=bytearray(length)
    for i,b in enumerate(NEEDLE):
     if address<=start+i<address+length:data[start+i-address]=b
    return bytes(data)
  with patch('tracker.process_memory.validate_anchor',return_value=0xabcdef):self.assertEqual(discover_ram(Process()),0xabcdef)

 def test_small_regions_are_scanned(self):
  class Small:
   def regions(self):return [(0x100000000,4096)]
   def read(self,a,n):return bytes(64)+NEEDLE+bytes(n-64-len(NEEDLE))
  with patch('tracker.process_memory.validate_anchor',return_value=0x123456):self.assertEqual(discover_ram(Small()),0x123456)
 def test_rejection_diagnostics(self):
  class Small:
   def regions(self):return [(0x100000000,4096)]
   def read(self,a,n):return bytes(64)+NEEDLE+bytes(n-64-len(NEEDLE))
  with patch('tracker.process_memory.validate_anchor',side_effect=ValueError('Checksum incorrecto')):
   with self.assertRaises(DiscoveryError) as caught:discover_ram(Small())
  self.assertEqual(caught.exception.diagnostic['signatures_found'],1)
  self.assertEqual(caught.exception.diagnostic['rejections'][0]['reason'],'Checksum incorrecto')

 def test_real_capture_signature_offset(self):
  # Wrapper has a vtable word at +64; the PK7 pointer starts at +68.
  raw=bytearray(party_data());struct.pack_into('<I',raw,64,0x00647348)
  p=FakeProcess();p.party=bytes(raw)
  self.assertEqual(validate_anchor(p,p.base+PARTY-LINEAR),p.base)
  c=self.connector();c.process=p
  self.assertEqual(c.read(PARTY,2914),bytes(raw))

 def test_dynamic_party_at_other_guest_address(self):
  from tracker.process_memory import discover_dynamic_ram
  class Dynamic:
   def __init__(self):
    self.base=0x100000000;self.guest=PARTY+0x2400;self.anchor=self.base+self.guest-LINEAR
    self.data=bytearray(party_data());struct.pack_into('<III',self.data,68,self.guest+128,self.guest+472,self.guest+408)
   def regions(self):return [(self.anchor-100,4096)]
   def read(self,address,length):
    out=bytearray(length)
    lo=max(address,self.anchor);hi=min(address+length,self.anchor+len(self.data))
    if hi>lo:out[lo-address:hi-address]=self.data[lo-self.anchor:hi-self.anchor]
    return bytes(out)
  p=Dynamic();self.assertEqual(discover_dynamic_ram(p),(p.base,p.guest))

 def test_dynamic_discovery_can_be_cancelled(self):
  from tracker.process_memory import discover_dynamic_ram,DiscoveryCancelled
  class Empty:
   def regions(self):return [(0x1000,4096)]
   def read(self,address,length):return bytes(length)
  with self.assertRaises(DiscoveryCancelled):discover_dynamic_ram(Empty(),cancel=lambda:True)
