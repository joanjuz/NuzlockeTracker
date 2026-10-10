"""Gen6 routes use the same validated PK6 met-location IDs as Pokémon records."""
import unittest
from tracker.reference import ReferenceData
from tracker.locations import TABLES, location_name


class Gen6RoutesTests(unittest.TestCase):
    def setUp(self):
        self.ref=ReferenceData()

    def test_shared_region_catalog_but_separate_game_and_progress_identity(self):
        for left,right,region,named_routes,expected in (
            ('Pokémon X 1.0','Pokémon Y 1.0','Kalos',range(1,23),80),
            ('Omega Ruby 1.0','Alpha Sapphire 1.0','Hoenn',range(101,135),92)):
            with self.subTest(region=region):
                x,y=self.ref.routes(left),self.ref.routes(right)
                self.assertEqual(x['region'],region)
                self.assertEqual(y['region'],region)
                self.assertEqual(x['routes'],y['routes'])
                self.assertNotEqual(x['game_key'],y['game_key'])
                self.assertEqual(x['game'],left)
                self.assertEqual(y['game'],right)
                self.assertEqual(len(x['routes']),expected)
                names={r['name'] for r in x['routes']}
                self.assertTrue({f'Ruta {n}' for n in named_routes}.issubset(names))

    def test_catalog_ids_are_unique_real_pkhex_span_and_include_other_zones(self):
        source=TABLES[6][0]
        for game,minimum,maximum,version,region in (
            ('Pokémon X 1.0',6,168,24,'Kalos'),
            ('Pokémon Y 1.0',6,168,25,'Kalos'),
            ('Omega Ruby 1.0',170,354,26,'Hoenn'),
            ('Alpha Sapphire 1.0',170,354,27,'Hoenn')):
            with self.subTest(game=game):
                routes=self.ref.routes(game)['routes']
                self.assertEqual(len({r['id'] for r in routes}),len(routes))
                self.assertEqual([r['story_order'] for r in routes],list(range(1,len(routes)+1)))
                for r in routes:
                    self.assertEqual(r['ids'],[r['id']])
                    self.assertEqual(r['id']%2,0)
                    self.assertTrue(minimum<=r['id']<=maximum)
                    self.assertEqual(r['name'],source[r['id']])
                    self.assertTrue(location_name(r['id'],version).startswith(r['name']))
                self.assertEqual(self.ref.routes(game)['region'],region)

    def test_no_usum_regression_or_mixed_regional_catalogs(self):
        usum=self.ref.routes('Ultra Moon 1.0')
        self.assertEqual(len(usum['routes']),90)
        self.assertEqual(self.ref.routes('Ultra Sun 1.0')['region'],usum['region'])
        self.assertEqual(self.ref.routes('Pokémon X 1.0')['routes'][0]['id'],6)
        self.assertEqual(self.ref.routes('Omega Ruby 1.0')['routes'][0]['id'],170)
        self.assertEqual(self.ref.routes('No implementado')['routes'],[])
