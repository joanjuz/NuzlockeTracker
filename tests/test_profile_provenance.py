"""Optional profile provenance: validation, actual import persistence and run isolation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tracker.game_data import GameDataManager, validate_document
from tracker.profile_provenance import profile_provenance_summary, validated_profile_provenance
from tracker.service import TrackerService

FIXTURE = Path(__file__).parent/'fixtures'/'definitive-game-data-v1.profile-provenance.synthetic.json'


def document():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class ProfileProvenanceValidationTests(unittest.TestCase):
    def test_declared_history_never_certifies_current_state(self):
        doc = document()
        block = validated_profile_provenance(doc['profileProvenance'], 'ultra-sun')
        self.assertEqual(block, doc['profileProvenance'])
        summary = profile_provenance_summary(doc)
        self.assertEqual((summary['state'], summary['name'], summary['author'], summary['currentMatch']),
                         ('historical', 'Randomizado de ejemplo', 'Autor de ejemplo', 'not-verified'))
        summary['sections'].clear()
        self.assertEqual(len(doc['profileProvenance']['sections']), 3)

    def test_absent_future_and_invalid_are_distinct_without_losing_other_data(self):
        doc = document()
        del doc['profileProvenance']
        self.assertEqual(profile_provenance_summary(doc)['state'], 'absent')
        for block in ({'version':2,'future':{'x':1}}, None, [], {'version':True}):
            with self.subTest(block=block):
                candidate = dict(doc, profileProvenance=block)
                accepted = validate_document(json.dumps(candidate))
                self.assertEqual(accepted['species'], doc['species'])
                self.assertEqual(accepted['playerLevelCaps'], doc['playerLevelCaps'])
                summary = profile_provenance_summary(accepted)
                self.assertEqual(summary['state'], 'ignored')
                self.assertIn('más nueva' if isinstance(block,dict) and block.get('version')==2 else 'no es válida', summary['reason'])

    def test_invalid_partitions_are_isolated(self):
        base = document()
        cases = [
            ('wrong game',lambda b:b.update(gameId='ultra-moon')),
            ('exact assertion',lambda b:b.update(currentMatch='exact')),
            ('unknown status',lambda b:b.update(status='verified')),
            ('bad changes',lambda b:b.update(subsequentChanges='unknown')),
            ('unknown field',lambda b:b.update(secret='private')),
            ('missing name',lambda b:b['profile'].pop('name')),
            ('empty author',lambda b:b['profile'].update(author='')),
            ('trim',lambda b:b['profile'].update(name=' name')),
            ('control',lambda b:b['profile'].update(name='name\n')),
            ('del',lambda b:b['profile'].update(name='name\x7f')),
            ('path',lambda b:b['profile'].update(name='D:\\private')),
            ('url',lambda b:b['profile'].update(author='https://private')),
            ('too long name',lambda b:b['profile'].update(name='n'*121)),
            ('too long author',lambda b:b['profile'].update(author='a'*81)),
            ('hash case',lambda b:b['profile'].update(recipeSha256='a'*64)),
            ('hash length',lambda b:b['profile'].update(recipeSha256='A'*63)),
            ('bool profile version',lambda b:b['profile'].update(version=True)),
            ('profile format',lambda b:b['profile'].update(format='other')),
            ('empty sections',lambda b:b.update(sections=[])),
            ('duplicate sections',lambda b:b.update(sections=['actions/a','actions/a'])),
            ('unordered sections',lambda b:b.update(sections=['actions/b','actions/a'])),
            ('too many',lambda b:b.update(sections=[f'actions/a{i:02}' for i in range(65)])),
            ('nested',lambda b:b.update(sections=[{'nested':{'x':1}}])),
            ('invalid section',lambda b:b.update(sections=['resources/private'])),
            ('section boundary',lambda b:b.update(sections=['actions/'+'a'*81])),
        ]
        for name, mutate in cases:
            with self.subTest(case=name):
                doc=copy.deepcopy(base); mutate(doc['profileProvenance'])
                self.assertEqual(profile_provenance_summary(validate_document(json.dumps(doc)))['state'],'ignored')

    def test_boundaries_and_modified_history(self):
        doc=document(); b=doc['profileProvenance']
        b['profile'].update(name='n'*120,author='a'*80)
        b['sections']=[f'actions/a{i:02}' for i in range(64)]
        b['subsequentChanges']='recorded'
        self.assertEqual(len(profile_provenance_summary(doc)['sections']),64)
        self.assertEqual(profile_provenance_summary(doc)['subsequentChanges'],'recorded')
        del b['profile']['author']
        self.assertIsNone(profile_provenance_summary(doc)['author'])
        b['version']=2; b['future']='x'*(16*1024)
        self.assertIn('no es válida',profile_provenance_summary(doc)['reason'])


class ProfileProvenancePersistenceTests(unittest.TestCase):
    def test_preview_confirm_reopen_replace_absent_remove_and_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'run-a'/'definitive-game-data.json'
            m=GameDataManager(path); doc=document(); raw=json.dumps(doc)
            preview=m.preview(raw,'Ultra Sun 1.0',lambda _:[])
            self.assertEqual(preview['profileProvenance']['name'],'Randomizado de ejemplo')
            self.assertFalse(path.exists())
            self.assertIsNone(m.status('Ultra Sun 1.0')['profileProvenance'])
            m.apply(preview['previewToken'],'Ultra Sun 1.0',True)
            reopened=GameDataManager(path)
            self.assertEqual(reopened.status('Ultra Sun 1.0')['profileProvenance'],preview['profileProvenance'])
            self.assertIsNone(reopened.status('Ultra Moon 1.0')['profileProvenance'])
            self.assertIsNone(GameDataManager(path.parent.parent/'run-b'/'definitive-game-data.json').document)
            old=path.read_bytes()
            replacement=copy.deepcopy(doc); replacement['profileProvenance']['profile']['name']='Otro perfil'
            candidate=reopened.preview(json.dumps(replacement),'Ultra Sun 1.0',lambda _:[])
            self.assertEqual(path.read_bytes(),old)
            with patch('tracker.game_data.os.replace',side_effect=OSError('locked')):
                with self.assertRaises(OSError):reopened.apply(candidate['previewToken'],'Ultra Sun 1.0',True)
            self.assertEqual(path.read_bytes(),old)
            self.assertEqual(reopened.status('Ultra Sun 1.0')['profileProvenance']['name'],'Randomizado de ejemplo')
            del replacement['profileProvenance']
            candidate=reopened.preview(json.dumps(replacement),'Ultra Sun 1.0',lambda _:[])
            reopened.apply(candidate['previewToken'],'Ultra Sun 1.0',True)
            self.assertEqual(GameDataManager(path).status('Ultra Sun 1.0')['profileProvenance']['state'],'absent')
            reopened.remove('Ultra Sun 1.0'); self.assertFalse(path.exists())

    def test_real_service_snapshot_keeps_accepted_caps_and_other_run_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); service=TrackerService(root/'a'/'state.json')
            service.update(game='Ultra Sun 1.0',party=[None]*6,stale=True)
            service.handle({'action':'level_caps_set','stages':[{'id':'one','name':'Mis límites','cap':35}]})
            before=copy.deepcopy(service.snapshot()['level_caps'])
            preview=service.preview_game_data(FIXTURE.read_text(encoding='utf-8'),'Ultra Sun 1.0')
            service.apply_game_data(preview['previewToken'],'Ultra Sun 1.0',True)
            snapshot=service.snapshot()
            self.assertEqual(snapshot['game_data']['profileProvenance']['name'],'Randomizado de ejemplo')
            self.assertEqual(snapshot['level_caps'],before)
            self.assertFalse((root/'b').exists())
            service.remove_game_data()
            self.assertEqual(service.snapshot()['level_caps'],before)


if __name__=='__main__':
    unittest.main()
