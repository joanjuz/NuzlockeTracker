"""Gen6 experimental PK6 party and candidate PC box support."""
import struct,tempfile,unittest
from pathlib import Path
from tracker.pokemon import decode_party,crypt
from tracker.profiles import PROFILES,GEN6_GAMES,capture_party
from tracker.process_memory import discover_dynamic_ram,LimeProcessMemory
from tracker.service import TrackerService


def party_fixture(game_version=24,species=25,address=0x08CE1CE8):
    raw=bytearray(2914)
    struct.pack_into('<III',raw,68,address+128,address+472,address+408)
    pk=bytearray(232)
    seed=0x1234
    struct.pack_into('<I',pk,0,seed)
    struct.pack_into('<H',pk,8,species)
    struct.pack_into('<I',pk,0x0C,0x12345678)
    pk[0xDF]=game_version
    pk[64:70]='Pika'.encode('utf-16-le')[:6]
    pk[0xDD]=5
    struct.pack_into('<H',pk,0xDA,8)
    struct.pack_into('<H',pk,6,sum(struct.unpack('<112H',pk[8:]))&0xffff)
    raw[128:360]=pk[:8]+crypt(pk[8:],seed)
    tail=bytearray(22)
    tail[4]=7
    struct.pack_into('<7H',tail,8,16,23,12,15,14,13,11)
    raw[472:494]=crypt(tail,seed)
    return bytes(raw)


class Reader:
    def __init__(self,address,snapshot):
        self.address=address
        self.snapshot=snapshot
    def read(self,address,length):
        if address!=self.address or length!=2914:
            raise ValueError('Lectura fuera de la dirección de equipo Gen6')
        return self.snapshot
    def close(self):pass


class Gen6Tests(unittest.TestCase):
    def test_profiles_point_to_unverified_guest_ram(self):
        self.assertEqual(len(GEN6_GAMES),4)
        for game in GEN6_GAMES:
            p=PROFILES[game]
            self.assertEqual((p.slot_stride,p.slot_size,p.generation,p.box_address),(484,484,6,0x08C861B8 if game=='Pokémon X 1.0' else 0x08C861C8 if game=='Pokémon Y 1.0' else 0x08C9A144))
            self.assertFalse(p.verified)
            self.assertEqual(p.party_address,0x08CE1CE8 if 'Pokémon ' in game else 0x08CF727C)
        self.assertEqual(PROFILES['Ultra Moon 1.0'].generation,7)
        self.assertNotEqual(PROFILES['Ultra Moon 1.0'].box_address,0)

    def test_pk6_decoding_and_gen6_species_cap(self):
        party=decode_party(party_fixture(),max_species=721)
        self.assertEqual(party[0]['species_id'],25)
        self.assertEqual(party[0]['origin_version'],24)
        self.assertEqual(party[0]['met_location_id'],8)
        self.assertEqual((party[0]['hp'],party[0]['max_hp']),(16,23))
        self.assertTrue(party[0]['checksum_valid'])
        self.assertEqual(party[1:],[None]*5)
        with self.assertRaises(ValueError):
            decode_party(party_fixture(species=722),max_species=721)

    def test_connect_and_poll_with_rejected_box_read_keeps_team_and_progress(self):
        versions={'Pokémon X 1.0':24,'Pokémon Y 1.0':25,
                  'Omega Ruby 1.0':26,'Alpha Sapphire 1.0':27}
        for name,version in versions.items():
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                path=Path(d)/'state.json'
                service=TrackerService(path)
                p=PROFILES[name]
                memory=Reader(p.party_address,party_fixture(version,address=p.party_address))
                service.factory=lambda config:memory
                service.config={'game':name,'mode':'gdb','port':24689}
                service.connect()
                self.assertIsNone(service.scan_next)
                self.assertFalse(service.snapshot()['scan']['active'])
                self.assertFalse(service.snapshot()['box_verified'])
                service.poll()
                state=service.snapshot()
                self.assertFalse(state['stale'])
                self.assertEqual(state['game'],name)
                self.assertEqual(state['party'][0]['species_id'],25)
                self.assertEqual(state['party'][0]['origin_version'],version)
                self.assertEqual(state['boxes'],{})
                self.assertFalse(state['battle_hp'])
                self.assertIn('Ruta 1',state['party'][0]['met_location'])
                self.assertNotIn('ultra-moon',service.progress.path.name)
                service.handle({'action':'scan'})
                self.assertEqual(service.scan_next,1)
                service.close_reader()

    def test_gen6_rejects_corrupt_team_before_reporting_connected(self):
        with tempfile.TemporaryDirectory() as d:
            service=TrackerService(Path(d)/'state.json')
            address=PROFILES['Pokémon X 1.0'].party_address
            service.factory=lambda cfg: Reader(address,bytes(2914))
            service.config={'game':'Pokémon X 1.0','mode':'gdb','port':24689}
            with self.assertRaises(ValueError):service.connect()

    def test_fast_gen6_region_probe_finds_valid_party_even_without_wrappers_in_scan(self):
        from tracker.process_memory import probe_gen6_region_ram
        class RegionProcess:
            def __init__(self):
                self.pid=33164
                self.name='lime3ds.exe'
                self.start=0x2aff0a20000
                self.base=self.start+64
                self.guest=0x08CE1C68
                self.anchor=self.base+self.guest-0x08000000
                self.payload=party_fixture(address=self.guest)
                self.calls=0
            def regions(self):return [(self.start,256*1024**2+4096)]
            def read(self,address,length):
                self.calls+=1
                if address==self.anchor and length==2914:return self.payload
                return bytes(length)
        process=RegionProcess()
        match,report=probe_gen6_region_ram(process)
        self.assertEqual(match,(process.base,process.guest))
        self.assertEqual(report['valid_candidates'],1)
        self.assertLess(process.calls,100)
        process.calls=0
        self.assertEqual(discover_dynamic_ram(process,generation=6),(process.base,process.guest))
        self.assertLess(process.calls,100)

    def test_region_probe_rejects_fake_party_signature_and_checksum(self):
        from tracker.process_memory import probe_gen6_region_ram
        class Process:
            def __init__(self):
                self.start=0x2aff0a20000
                self.anchor=self.start+64+0x08CE1C68-0x08000000
                self.invalid=bytearray(party_fixture(address=0x08CE1C68))
                self.invalid[128]^=1
            def regions(self):return [(self.start,256*1024**2+4096)]
            def read(self,address,length):
                return bytes(self.invalid) if (address,length)==(self.anchor,2914) else bytes(length)
        match,report=probe_gen6_region_ram(Process())
        self.assertIsNone(match)
        self.assertEqual(report['valid_candidates'],0)

    def test_dynamic_discovery_in_legacy_gen6_guest_ram(self):
        class Process:
            def __init__(self):
                self.pid=9;self.name='citra-qt.exe'
                self.base=0x100000000
                self.guest=0x08CE1CE8
                self.anchor=self.base+self.guest-0x08000000
                self.payload=party_fixture(address=self.guest)
            def regions(self):return [(self.anchor-96,4096)]
            def read(self,address,length):
                result=bytearray(length)
                low=max(address,self.anchor)
                high=min(address+length,self.anchor+len(self.payload))
                if high>low:result[low-address:high-address]=self.payload[low-self.anchor:high-self.anchor]
                return bytes(result)
            def alive(self):return True
            def close(self):pass
        p=Process()
        self.assertEqual(discover_dynamic_ram(p,generation=6),(p.base,p.guest))
        reader=LimeProcessMemory.__new__(LimeProcessMemory)
        reader.process=p;reader.base=p.base
        reader.generation=6;reader.guest_start=0x08000000;reader.guest_end=0x10000000
        reader.party_address=p.guest
        self.assertEqual(reader.read(p.guest,2914),p.payload)
        with self.assertRaises(ValueError):reader.read(0x30000000,1)
