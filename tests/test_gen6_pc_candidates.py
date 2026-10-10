"""Gen6 read-only box candidates from a verified guest-memory shift."""
import unittest
from tracker.gen6_pc import Gen6BoxProbe
from tracker.boxes import BOX_SIZE
from tracker.profiles import PROFILES
from test_gen6_compat import party_fixture

class Memory:
    def __init__(self,base,real,with_pokemon=True,unstable=False):
        self.base=base;self.real=real;self.with_pokemon=with_pokemon
        self.unstable=unstable;self.counter=0
        self.pk=party_fixture()[128:360]
    def read(self,address,length):
        if length!=BOX_SIZE or not self.real<=address<self.real+31*BOX_SIZE:
            raise ValueError('Zona no mapeada')
        box=(address-self.real)//BOX_SIZE
        if self.real+box*BOX_SIZE!=address:raise ValueError('Caja mal alineada')
        self.counter+=1
        if self.unstable and box==0 and self.counter%2==0:
            return bytes(BOX_SIZE)
        return (self.pk+bytes(BOX_SIZE-232)) if box==0 and self.with_pokemon else bytes(BOX_SIZE)

class Gen6CandidateTests(unittest.TestCase):
    def test_report_and_choose_shifted_base_only_after_all_31_boxes(self):
        profile=PROFILES['Pokémon X 1.0']
        delta=-128  # The real Lime3DS Pokémon X diagnosis from 2026-10-09.
        memory=Memory(profile.box_address,profile.box_address+delta)
        scan=Gen6BoxProbe(profile.box_address,delta)
        self.assertEqual(scan.addresses,(profile.box_address,profile.box_address-128))
        for n in range(1,31):scan.read(memory,n)
        with self.assertRaises(ValueError):scan.finish()
        scan.read(memory,31)
        chosen,boxes=scan.finish()
        self.assertEqual(chosen,profile.box_address-128)
        self.assertEqual(len(boxes),31)
        self.assertEqual(boxes['1'][0]['species_id'],25)
        diagnostics=scan.diagnostic()
        self.assertEqual(len(diagnostics),2)
        self.assertEqual(diagnostics[0]['first_rejection_box'],1)
        self.assertEqual(diagnostics[1]['pokemon_verified'],1)
        self.assertNotIn('nickname',str(diagnostics))
        self.assertNotIn('ot_id',str(diagnostics))

    def test_rejects_empty_pc_and_torn_box_snapshot(self):
        profile=PROFILES['Pokémon X 1.0']
        for kwargs in ({'with_pokemon':False},{'unstable':True}):
            with self.subTest(kwargs=kwargs):
                memory=Memory(profile.box_address,profile.box_address-128,**kwargs)
                scan=Gen6BoxProbe(profile.box_address,-128)
                for n in range(1,32):scan.read(memory,n)
                self.assertEqual(scan.finish(),(None,None))
                self.assertTrue(scan.diagnostic())

    def test_invalid_bounds_duplicate_candidates_and_order(self):
        p=PROFILES['Pokémon X 1.0']
        scan=Gen6BoxProbe(p.box_address,0)
        self.assertEqual(len(scan.addresses),1)
        with self.assertRaises(ValueError):scan.read(Memory(0,0),3)
        with self.assertRaises(ValueError):Gen6BoxProbe(0,0)
