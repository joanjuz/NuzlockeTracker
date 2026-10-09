import unittest
from tracker.reference import ReferenceData
from tracker.catalog import Catalog
class ReferenceTests(unittest.TestCase):
 def setUp(self):self.ref=ReferenceData();self.catalog=Catalog()
 def test_complete_usum_move_catalog(self):
  self.assertEqual(len(self.ref.moves),728)
  for id in range(1,729):
   m=self.ref.move(id,self.catalog);self.assertTrue(m['description']);self.assertIn(m['category'],('Estado','Físico','Especial'));self.assertGreater(m['pp'],0)
 def test_generation_seven_healing_pp(self):
  for id in (105,355,208):self.assertEqual(self.ref.move(id,self.catalog)['pp'],10)
  self.assertIsNone(self.ref.move(355,self.catalog)['power'])
 def test_scald(self):
  m=self.ref.move(503,self.catalog);self.assertEqual((m['type'],m['category'],m['power'],m['pp']),('Agua','Especial',80,15))
 def test_rom_metadata_overrides_reference(self):
  self.catalog.custom={'label':'Prueba','moves':{'503':{'power':90,'pp':20}}};m=self.ref.move(503,self.catalog)
  self.assertEqual(m['power'],90);self.assertTrue(m['rom_override']);self.assertEqual(self.ref.moves['503']['power'],80)
 def test_route_registry_includes_all_numbered_routes(self):
  routes=self.ref.routes('Ultra Moon 1.0')['routes'];self.assertEqual(len({r['id'] for r in routes}),len(routes))
  self.assertEqual({r['name'] for r in routes if r['name'].startswith('Ruta ') and r['name'].split()[-1].isdigit()},{f'Ruta {i}' for i in range(1,18)})
  self.assertEqual(self.ref.routes('Juego no implementado')['routes'],[])

 def test_story_order_and_ids_survive_coalescing(self):
  routes=self.ref.routes('Ultra Moon 1.0')['routes'];names=[r['name'] for r in routes]
  self.assertLess(names.index('Ruta 11'),names.index('Ruta 10'))
  self.assertLess(names.index('Ruta 15'),names.index('Ruta 14'))
  self.assertEqual(sum(len(r['ids']) for r in routes),109)
  self.assertEqual(next(r for r in routes if r['name']=='Ciudad Hauoli')['ids'],[18,20,22])
 def test_usum_forms_have_correct_types(self):
  self.assertEqual(self.ref.pokemon_types(637,0),['Bicho','Fuego'])
  self.assertEqual(self.ref.pokemon_types(282,0),['Psíquico','Hada'])
  self.assertEqual(self.ref.pokemon_types(19,1),['Siniestro','Normal'])
