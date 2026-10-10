"""Read-only Gen6 PC validation. Fixtures do not claim hardware validation."""
import tempfile
import unittest
from pathlib import Path
from tracker.boxes import BOX_SIZE,decode_box,read_box
from tracker.profiles import PROFILES
from tracker.service import TrackerService
from test_gen6_compat import party_fixture


class Gen6Memory:
    def __init__(self, profile, with_box=True, corrupt=False, torn=False):
        self.profile=profile
        self.party=party_fixture(26 if 'Ruby' in profile.name else 24,
            address=profile.party_address)
        self.read_count={}
        self.corrupt=corrupt
        self.torn=torn
        self.box_base=profile.box_address
        self.box1=(self.party[128:360]+bytes(BOX_SIZE-232)) if with_box else bytes(BOX_SIZE)

    def read(self,addr,size):
        if addr==self.profile.party_address and size==2914:
            return self.party
        index=(addr-self.box_base)//BOX_SIZE
        if size==BOX_SIZE and 0<=index<31 and addr==self.box_base+index*BOX_SIZE:
            self.read_count[index]=self.read_count.get(index,0)+1
            if index==0:
                if self.corrupt:return bytes(4)+bytes([1])+bytes(BOX_SIZE-5)
                if self.torn and self.read_count[index]%2==0:
                    return bytes(BOX_SIZE)
                return self.box1
            return bytes(BOX_SIZE)
        raise ValueError('PC fuera de dirección candidata')
    def close(self):pass


class Gen6BoxesTests(unittest.TestCase):
    def test_one_pk6_box_slot_and_gen6_31_bounds(self):
        x=PROFILES['Pokémon X 1.0']
        m=Gen6Memory(x)
        decoded=decode_box(read_box(m,1,x.box_address,box_count=31),max_species=721)
        self.assertEqual(decoded[0]['species_id'],25)
        self.assertEqual(decoded[1:],[None]*29)
        with self.assertRaises(ValueError):read_box(m,32,x.box_address,box_count=31)

    def test_31_boxes_published_only_after_checksum_validated_full_scan(self):
        for game in ('Pokémon X 1.0','Omega Ruby 1.0'):
            with self.subTest(game=game),tempfile.TemporaryDirectory() as folder:
                profile=PROFILES[game]
                m=Gen6Memory(profile)
                app=TrackerService(Path(folder)/'state.json')
                app.factory=lambda config:m
                app.config={'game':game,'mode':'memory'}
                app.connect()
                self.assertFalse(app.snapshot()['box_verified'])
                for i in range(30):
                    app.poll()
                    self.assertEqual(app.snapshot()['boxes'],{})
                    self.assertFalse(app.snapshot()['box_verified'])
                self.assertEqual(app.scan_next,31)
                app.poll()
                state=app.snapshot()
                self.assertEqual(state['scan'],{'active':False,'completed':31})
                self.assertTrue(state['box_verified'])
                self.assertEqual(len(state['boxes']),31)
                self.assertEqual(len(state['boxes']['31']),30)
                self.assertEqual(state['boxes']['1'][0]['species_id'],25)
                self.assertEqual(m.read_count[0],2)
                self.assertIn('cajas PK6',state['connection']['message'])
                self.assertNotIn('full_scan_baseline',state['boxes'])
                self.assertFalse(state['battle_hp'])

    def test_no_evidence_or_torn_read_cannot_publish_fantasy_boxes(self):
        for kwargs in ({'with_box':False},{'torn':True},{'corrupt':True}):
            with self.subTest(kwargs=kwargs),tempfile.TemporaryDirectory() as folder:
                p=PROFILES['Pokémon Y 1.0']
                m=Gen6Memory(p,**kwargs)
                service=TrackerService(Path(folder)/'state.json')
                service.factory=lambda cfg:m
                service.config={'game':p.name,'mode':'memory'}
                service.connect()
                for _ in range(31):service.poll()
                state=service.snapshot()
                self.assertEqual(state['boxes'],{})
                self.assertFalse(state['box_verified'])
                self.assertEqual(state['party'][0]['species_id'],25)
                self.assertFalse(state['scan']['active'])
                self.assertIn('no verificadas',state['connection']['message'])
                # User can explicitly request retry after putting a Pokémon in PC.
                m.corrupt=False;m.torn=False;m.box1=m.party[128:360]+bytes(BOX_SIZE-232)
                service.handle({'action':'scan'})
                for _ in range(31):service.poll()
                self.assertTrue(service.snapshot()['box_verified'])
