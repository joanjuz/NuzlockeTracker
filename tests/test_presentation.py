import unittest
from tracker.presentation import stat_text,move_text
class PresentationTests(unittest.TestCase):
 def test_stat_mapping_includes_specials(self):
  p={'stats':dict(ATQ=309,DEF=170,ATE=262,DEE=194,VEL=232)}
  self.assertEqual(stat_text(p),'Ataque: 309\nDefensa: 170\nAt. especial: 262\nDef. especial: 194\nVelocidad: 232')
 def test_missing_stats(self):self.assertIn('At. especial: —',stat_text({'stats':None}))
 def test_all_four_moves(self):
  class Names:
   def name(self,section,id):return str(id)
  self.assertEqual(move_text({'moves':[1,2,3,4]},Names()),'1. 1\n2. 2\n3. 3\n4. 4')
