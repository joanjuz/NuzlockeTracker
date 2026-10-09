import json,tempfile,unittest
from pathlib import Path
from tracker.catalog import Catalog
class CatalogTests(unittest.TestCase):
 def test_all_usum_names(self):
  c=Catalog()
  for section,count in [('species',808),('moves',729),('abilities',234),('items',960)]:
   self.assertGreaterEqual(len(c.names[section]),count)
   self.assertTrue(all(c.names[section][i] for i in range(count)))
  self.assertEqual(c.name('species',637),'Volcarona')
  self.assertEqual(c.name('abilities',144),'Regeneración')
  self.assertIn('ID',c.name('moves',999999))
 def test_override_and_atomic_validation(self):
  c=Catalog()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'custom.json'
   good={'schema_version':1,'game':'Ultra Moon 1.0','label':'Prueba','moves':{'503':{'name':'Movimiento personalizado','power':30,'type':'Fuego'}}}
   p.write_text(json.dumps(good));c.load(p)
   self.assertEqual(c.name('moves',503),'Movimiento personalizado')
   self.assertEqual(c.metadata('moves',503)['power'],30)
   bad={**good,'moves':{'503':{'power':'30'}}};p.write_text(json.dumps(bad))
   with self.assertRaises(ValueError):c.load(p)
   self.assertEqual(c.name('moves',503),'Movimiento personalizado')
 def test_wrong_game(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'custom.json';p.write_text('{"schema_version":1,"game":"Ultra Sun 1.0","label":"Test"}')
   with self.assertRaises(ValueError): Catalog().load(p)
