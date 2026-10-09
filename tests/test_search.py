import unittest
from tracker.search import matches,normalized
class Catalog:
 def name(self,section,id):return {'species':'Volcarona','abilities':'Regeneración','items':'Pañuelo Elección','moves':'Voltiocambio'}[section]
class SearchTests(unittest.TestCase):
 def setUp(self):self.p=dict(nickname='Botella',species_id=637,ability_id=144,item_id=287,moves=[521]);self.c=Catalog()
 def test_accents_case(self):self.assertTrue(matches(self.p,'REGENERACION',self.c))
 def test_multiple_terms(self):self.assertTrue(matches(self.p,'volcarona botella',self.c))
 def test_move_and_item(self):self.assertTrue(matches(self.p,'voltiocambio eleccion',self.c))
 def test_no_match(self):self.assertFalse(matches(self.p,'milotic',self.c))
 def test_blank(self):self.assertTrue(matches(self.p,'  ',self.c))
