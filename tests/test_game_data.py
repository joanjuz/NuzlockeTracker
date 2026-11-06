"""Synthetic DGD contract, persistence, precedence and real local HTTP coverage."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from server import TrackerHTTPServer, make_handler
from tracker.game_data import GameDataManager, MAX_BYTES, TYPE_NAMES, validate_document
from tracker.service import TrackerService


def document(game='ultra-moon'):
    return {'format':'PokeJuz.DefinitiveGameData','schemaVersion':1,
        'producer':{'id':'DefinitiveRandomizer','version':'synthetic-test'},
        'game':{'id':game,'generation':7,'titleId':'00040000001B5100' if game=='ultra-moon' else '00040000001B5000',
                'revision':None,'revisionStatus':'unknown'},
        'source':{'kind':'saved-project','fingerprintAlgorithm':'SHA-256','fingerprint':'A'*64,
                  'scope':'personal,moves,evolutions,gametext'},'coverage':'exported-records',
        'types':[{'id':i,'name':name} for i,name in enumerate(TYPE_NAMES)],
        'abilities':[{'id':0,'name':'Sin habilidad'},{'id':65,'name':'Habilidad sintética'}],
        'species':[{'speciesId':1,'formId':0,'personalIndex':1,'name':'Especie sintética',
                    'types':[9,9],'abilities':[65,65,0],
                    'baseStats':{'hp':123,'attack':141,'defense':70,'specialAttack':65,'specialDefense':70,'speed':75}}],
        'moves':[{'id':1,'name':'Movimiento sintético','typeId':9,'category':1,'power':137,
                  'accuracy':100,'pp':15,'priority':-2}],
        'evolutions':[{'speciesId':1,'formId':0,'routes':[{'method':4,'argument':0,'targetSpeciesId':3,'targetFormId':0,'level':27}]}]}


class GameDataValidationTests(unittest.TestCase):
    def test_accepts_optional_extensions_boundaries_and_shared_cosmetic_index(self):
        doc=document();doc['futureMetadata']={'author':'Synthetic'}
        form=copy.deepcopy(doc['species'][0]);form.update(formId=1)
        form['baseStats']['hp']=0;form['baseStats']['speed']=255
        doc['species'].append(form)
        doc['moves'][0].update(accuracy=255,pp=0,priority=-8)
        parsed=validate_document(json.dumps(doc))
        self.assertEqual(parsed['species'][1]['personalIndex'],1)
        self.assertEqual(parsed['futureMetadata'],{'author':'Synthetic'})
        self.assertEqual((parsed['moves'][0]['accuracy'],parsed['moves'][0]['pp']), (255,0))

    def test_rejects_wrong_schema_game_identity_and_revisions(self):
        mutations=[('schemaVersion',2),('schemaVersion',True),('format','other')]
        for field,value in mutations:
            with self.subTest(field=field,value=value):
                doc=document();doc[field]=value
                with self.assertRaises(ValueError):validate_document(json.dumps(doc))
        for mutation in ({'id':'pokemon-x'},{'id':[]},{'generation':True},
                         {'titleId':'00040000001B5000'},{'revision':'1.2','revisionStatus':'known'},
                         {'revision':'1.0','revisionStatus':'unknown'}):
            with self.subTest(mutation=mutation):
                doc=document();doc['game'].update(mutation)
                with self.assertRaises(ValueError):validate_document(json.dumps(doc))

    def test_rejects_invalid_tables_duplicates_and_references(self):
        cases=[('duplicate species',lambda d:d['species'].append(copy.deepcopy(d['species'][0]))),
               ('duplicate move',lambda d:d['moves'].append(copy.deepcopy(d['moves'][0]))),
               ('duplicate type',lambda d:d['types'][1].update(id=0)),
               ('duplicate evolution',lambda d:d['evolutions'].append(copy.deepcopy(d['evolutions'][0]))),
               ('missing type',lambda d:d['types'].pop()),
               ('empty species',lambda d:d.update(species=[])),
               ('unknown ability',lambda d:d['species'][0].update(abilities=[233,65,0])),
               ('bool stat',lambda d:d['species'][0]['baseStats'].update(hp=True)),
               ('bad form',lambda d:d['species'][0].update(formId=32)),
               ('bad power',lambda d:d['moves'][0].update(power=256)),
               ('bad priority',lambda d:d['moves'][0].update(priority=9)),
               ('bad evolution',lambda d:d['evolutions'][0]['routes'][0].update(targetSpeciesId=808)),
               ('unknown evolution source',lambda d:d['evolutions'][0].update(speciesId=807)),
               ('fingerprint',lambda d:d['source'].update(fingerprint='x'*64)),
               ('control label',lambda d:d['species'][0].update(name='a\nb'))]
        for label,mutate in cases:
            with self.subTest(case=label):
                doc=document();mutate(doc)
                with self.assertRaises(ValueError):validate_document(json.dumps(doc))

    def test_rejects_truncation_duplicate_json_keys_and_oversized_files(self):
        for raw in ('{','{"schemaVersion":1,"schemaVersion":1}', ' '* (MAX_BYTES+1)):
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(ValueError):validate_document(raw)


class GameDataManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'run-a'/'definitive-game-data.json'
        self.manager=GameDataManager(self.path)

    def preview(self,doc=None,game='Ultra Moon 1.0'):
        return self.manager.preview(json.dumps(doc or document()),game,lambda d:[{'after':d['species'][0]['baseStats']['hp']}])

    def test_preview_is_read_only_apply_requires_confirmation_and_reopens(self):
        preview=self.preview()
        self.assertFalse(self.path.exists());self.assertIsNone(self.manager.document)
        self.assertEqual(preview['differences'],[{'after':123}])
        self.assertTrue(preview['requiresRevisionAcknowledgement'])
        with self.assertRaisesRegex(ValueError,'Confirma'):self.manager.apply(preview['previewToken'],'Ultra Moon 1.0')
        self.manager.apply(preview['previewToken'],'Ultra Moon 1.0',True)
        reopened=GameDataManager(self.path)
        self.assertEqual(reopened.species(1,0,'Ultra Moon 1.0')['baseStats']['hp'],123)
        self.assertIsNone(reopened.species(1,0,'Ultra Sun 1.0'))

    def test_preview_rejects_other_game_and_stale_token(self):
        with self.assertRaisesRegex(ValueError,'juego'):self.preview(game='Ultra Sun 1.0')
        first=self.preview();second=self.preview()
        with self.assertRaisesRegex(ValueError,'caducó'):self.manager.apply(first['previewToken'],'Ultra Moon 1.0',True)
        with self.assertRaisesRegex(ValueError,'otro juego'):self.manager.apply(second['previewToken'],'Ultra Sun 1.0',True)
        self.assertFalse(self.path.exists())

    def test_known_revision_and_successful_replacement_do_not_require_unknown_ack(self):
        doc=document();doc['game'].update(revisionStatus='known',revision='1.0')
        first=self.preview(doc);self.manager.apply(first['previewToken'],'Ultra Moon 1.0')
        doc['species'][0]['baseStats']['hp']=200
        second=self.preview(doc)
        self.assertTrue(second['replacesExisting'])
        self.assertFalse(second['requiresRevisionAcknowledgement'])
        self.manager.apply(second['previewToken'],'Ultra Moon 1.0')
        self.assertEqual(GameDataManager(self.path).species(1,0,'Ultra Moon 1.0')['baseStats']['hp'],200)

    def test_atomic_failed_replace_and_remove_preserve_previous_import(self):
        self.manager.apply(self.preview()['previewToken'],'Ultra Moon 1.0',True)
        original=self.path.read_bytes();doc=document();doc['species'][0]['baseStats']['hp']=200
        second=self.preview(doc)
        with patch('tracker.game_data.os.replace',side_effect=OSError('locked')):
            with self.assertRaises(OSError):self.manager.apply(second['previewToken'],'Ultra Moon 1.0',True)
        self.assertEqual(self.path.read_bytes(),original)
        self.assertEqual(self.manager.species(1,0,'Ultra Moon 1.0')['baseStats']['hp'],123)
        with patch.object(Path,'unlink',side_effect=OSError('locked')):
            with self.assertRaises(OSError):self.manager.remove('Ultra Moon 1.0')
        self.assertTrue(self.manager.status('Ultra Moon 1.0')['loaded'])
        self.manager.remove('Ultra Moon 1.0')
        self.assertFalse(self.path.exists());self.assertFalse(self.manager.status('Ultra Moon 1.0')['loaded'])

    def test_damaged_cache_does_not_prevent_startup_or_touch_other_files(self):
        self.path.parent.mkdir();self.path.write_text('{bad',encoding='utf-8')
        other=self.path.parent/'state.json';other.write_text('untouched')
        loaded=GameDataManager(self.path)
        self.assertIsNone(loaded.document);self.assertIn('No se pudo cargar',loaded.error)
        self.assertEqual(other.read_text(),'untouched')


class GameDataServiceTests(unittest.TestCase):
    def test_canonical_synthetic_fixture_imports_without_cross_repo_dependency(self):
        # Golden copy of the producer's public synthetic contract example.
        raw=(Path(__file__).parent/'fixtures'/'definitive-game-data-v1.synthetic.json').read_text(encoding='utf-8-sig')
        with tempfile.TemporaryDirectory() as folder:
            service=TrackerService(Path(folder)/'state.json')
            service.update(game='Ultra Sun 1.0',party=[{'species_id':1,'form':0,'moves':[1,0,0,0]}]+[None]*5,stale=True)
            preview=service.preview_game_data(raw,'Ultra Sun 1.0');service.apply_game_data(preview['previewToken'],'Ultra Sun 1.0',True)
            mon=service.snapshot()['party'][0]
            self.assertEqual((mon['base_stats']['HP'],mon['base_stats']['ATK'],mon['types']),(123,141,['Fuego']))
            self.assertEqual((mon['analysis_moves'][0]['power'],mon['analysis_moves'][0]['priority']),(137,-2))
            self.assertEqual((mon['evolutions'][0]['target'],mon['evolutions'][0]['target_name']),(2,'Especie sintética B'))
            self.assertIn('27',mon['evolutions'][0]['method'])

    def test_full_import_display_reopen_profile_isolation_and_remove_restores_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);service=TrackerService(root/'run-a'/'state.json')
            raw={'species_id':1,'form':0,'ability_id':65,'moves':[1,0,0,0], 'hp':17,'max_hp':55}
            service.update(party=[raw]+[None]*5,stale=True)
            service.import_templates({'moves':'Move,Power,PP\n1,88,20\n',
                                      'stats':'Entry,Pokemon,HP,ATK,DEF,SPA,SPD,SPE\n1,,99,90,90,90,90,90\n'})
            doc=document();target=copy.deepcopy(doc['species'][0])
            target.update(speciesId=3,personalIndex=3,name='Destino modificado')
            doc['species'].append(target)
            preview=service.preview_game_data(json.dumps(doc),'Ultra Moon 1.0')
            self.assertTrue(any(d['field']=='Tipos' for d in preview['differences']))
            self.assertFalse((root/'run-a'/'definitive-game-data.json').exists())
            service.apply_game_data(preview['previewToken'],'Ultra Moon 1.0',True)
            mon=service.snapshot()['party'][0]
            self.assertEqual((mon['types'],mon['base_stats']['HP'],mon['analysis_moves'][0]['power']),(['Fuego'],123,137))
            self.assertEqual((mon['ability'],mon['species_abilities'][0]['id']),('Habilidad sintética',65))
            self.assertEqual((mon['evolutions'][0]['target'],mon['evolutions'][0]['target_form']),(3,0))
            self.assertEqual(mon['evolutions'][0]['target_name'],'Destino modificado')
            self.assertIn('27',mon['evolutions'][0]['method'])
            self.assertEqual((mon['hp'],mon['max_hp']),(17,55))
            service.flush_state(force=True)
            reopened=TrackerService(service.output)
            self.assertEqual(reopened.snapshot()['party'][0]['base_stats']['HP'],123)
            other=TrackerService(root/'run-b'/'state.json')
            self.assertFalse(other.game_data.status('Ultra Moon 1.0')['loaded'])
            self.assertEqual(reopened.reference.move(1,reopened.catalog)['source'],'Definitive Game Data')
            reopened.remove_game_data()
            mon=reopened.snapshot()['party'][0]
            self.assertEqual((mon['base_stats']['HP'],mon['analysis_moves'][0]['power']),(99,88))
            self.assertNotEqual(mon['types'],['Fuego'])
            self.assertEqual(mon['type_source'],'Referencia USUM')
            self.assertNotIn('species_abilities',mon)

    def test_forms_explicit_no_evolutions_and_inactive_other_game(self):
        with tempfile.TemporaryDirectory() as folder:
            service=TrackerService(Path(folder)/'state.json')
            doc=document();form=copy.deepcopy(doc['species'][0]);form.update(formId=1,name='Forma sintética')
            form['types']=[10,10];doc['species'].append(form)
            doc['evolutions'].append({'speciesId':1,'formId':1,'routes':[]})
            p=service.preview_game_data(json.dumps(doc),'Ultra Moon 1.0');service.apply_game_data(p['previewToken'],'Ultra Moon 1.0',True)
            mon=service.refresh_template({'species_id':1,'form':1})
            self.assertEqual((mon['types'],mon['evolutions'],mon['species']),(['Agua'],[],'Forma sintética'))
            service.update(game='Ultra Sun 1.0',stale=True)
            self.assertNotEqual(service.refresh_template({'species_id':1,'form':1})['types'],['Agua'])
            self.assertFalse(service.game_data.status('Ultra Sun 1.0')['active'])

    def test_zero_level_special_evolution_is_rendered_without_assuming_a_level(self):
        with tempfile.TemporaryDirectory() as folder:
            service=TrackerService(Path(folder)/'state.json');doc=document()
            doc['evolutions'][0]['routes'][0].update(method=8,argument=84,level=0)
            p=service.preview_game_data(json.dumps(doc),'Ultra Moon 1.0');service.apply_game_data(p['previewToken'],'Ultra Moon 1.0',True)
            route=service.refresh_template({'species_id':1,'form':0})['evolutions'][0]
            self.assertIn('piedra agua',route['method'])
            self.assertNotIn('nivel',route['method'])


class GameDataApiTests(unittest.TestCase):
    def test_authenticated_preview_apply_status_and_remove(self):
        with tempfile.TemporaryDirectory() as folder:
            service=TrackerService(Path(folder)/'state.json')
            server=TrackerHTTPServer(('127.0.0.1',0),make_handler(service,'test'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def call(path,data=None,token='test'):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
                try:
                    connection.request('POST' if data is not None else 'GET',path,
                                       json.dumps(data) if data is not None else None,
                                       {'X-Tracker-Token':token,'Content-Type':'application/json'})
                    response=connection.getresponse();return response.status,json.loads(response.read())
                finally:connection.close()
            try:
                payload={'content':json.dumps(document()),'game':'Ultra Moon 1.0'}
                self.assertEqual(call('/api/game-data/preview',payload,'bad')[0],403)
                code,preview=call('/api/game-data/preview',payload);self.assertEqual(code,200)
                self.assertFalse(call('/api/game-data')[1]['loaded'])
                apply={'previewToken':preview['previewToken'],'game':'Ultra Moon 1.0'}
                self.assertEqual(call('/api/game-data/apply',apply)[0],400)
                apply['acknowledgeUnknownRevision']=True
                self.assertEqual(call('/api/game-data/apply',apply)[0],200)
                self.assertTrue(call('/api/game-data')[1]['active'])
                self.assertFalse(call('/api/game-data/remove',{})[1]['loaded'])
            finally:
                server.shutdown();server.server_close();thread.join();service.stop.set()


if __name__=='__main__':unittest.main()
