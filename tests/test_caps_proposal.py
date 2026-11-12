"""Level caps proposed by Definitive Randomizer (optional playerLevelCaps block of DGD v1).

Synthetic documents only. Covers the strict check of block version 1, blocks that are ignored
without invalidating the rest of the data, the proposal (never applied on its own), explicit
acceptance and replacement, dismissal, the separate provenance file, stale confirmations and
isolation between runs and games.
"""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from server import make_handler
from tracker.game_data import (GameDataManager, level_caps_summary, level_caps_table_sha256,
                               validate_document, validated_level_caps_block)
from tracker.level_caps_source import FORMAT as SOURCE_FORMAT, LevelCapsSource
from tracker.profiles import PROFILES
from tracker.progress import MAX_STAGES, level_caps_view, stages_revision
from tracker.service import FINAL_STAGE_NAME, TrackerService

FIXTURES = Path(__file__).parent / 'fixtures'
EXTENDED = FIXTURES / 'definitive-game-data-v1.player-level-caps.synthetic.json'
ORIGINAL = FIXTURES / 'definitive-game-data-v1.synthetic.json'
MOON, SUN = 'Ultra Moon 1.0', 'Ultra Sun 1.0'


def example(game='ultra-sun'):
    doc = json.loads(EXTENDED.read_text(encoding='utf-8'))
    doc['game'].update(id=game, titleId='00040000001B5100' if game == 'ultra-moon' else '00040000001B5000')
    return doc


def flag(byte, mask=1):
    return {'kind': 'event-flag-set', 'byte': byte, 'mask': mask}


def with_points(doc, points):
    """Replace the checkpoints (cap, condition[, label]) and recompute order and the table hash."""
    block = doc['playerLevelCaps']
    block['checkpoints'] = [{'order': i + 1, 'cap': cap, 'condition': condition,
                             **({'label': rest[0], 'labelSource': 'randomizer-catalog'} if rest else {})}
                            for i, (cap, condition, *rest) in enumerate(points)]
    block['source']['tableSha256'] = level_caps_table_sha256(block['checkpoints'])
    return doc


def not_installed(status, hooks, source=True, detail=None):
    block = {'version': 1, 'status': status, 'hooks': {'battleCro': hooks[0], 'codeBin': hooks[1]}}
    if source:
        block['source'] = {'fingerprintAlgorithm': 'SHA-256', 'scope': 'battle.cro,code.bin', 'fingerprint': 'B' * 64}
    if detail:
        block['detail'] = detail
    return block


class BlockValidationTests(unittest.TestCase):
    def test_fixture_is_the_published_contract_example(self):
        doc, original = example(), json.loads(ORIGINAL.read_text(encoding='utf-8'))
        self.assertEqual({k: v for k, v in doc.items() if k != 'playerLevelCaps'}, original)
        block = doc['playerLevelCaps']
        self.assertEqual(level_caps_table_sha256(block['checkpoints']), block['source']['tableSha256'])

    def test_installed_block_becomes_a_proposal_and_never_a_current_stage(self):
        summary = level_caps_summary(validate_document(json.dumps(example())))
        self.assertEqual((summary['state'], summary['status'], summary['count'], summary['ceiling']), ('proposal', 'installed', 6, 100))
        self.assertEqual([s['cap'] for s in summary['stages']], [15, 20, 45, 50, 60, 70])
        self.assertEqual(summary['stages'][0]['name'], 'Clear Normal Trial - Ilima (1dom)')
        # A condition outside the Randomizer catalog has no label: it is named by its condition, never invented.
        self.assertIsNone(summary['checkpoints'][3]['label'])
        self.assertEqual(summary['stages'][3]['name'], 'Event Flag · byte 0x0150, máscara 0x04')
        self.assertEqual(summary['checkpoints'][4]['conditionText'], 'Event Work 68 ≥ 1796')
        self.assertEqual(set(summary['stages'][0]), {'name', 'cap'})
        self.assertNotIn('current', summary)

    def test_other_statuses_are_diagnostics_without_any_list(self):
        cases = [not_installed('not-detected', ('stock', 'stock')),
                 not_installed('unsupported', ('applied', 'missing'), source=False, detail='code.bin falta'),
                 not_installed('unsupported', ('unrecognized', 'stock')),
                 not_installed('inconsistent', ('applied', 'stock')),
                 not_installed('inconsistent', ('applied', 'applied'), detail='tablas distintas'),
                 not_installed('legacy-format', ('applied-legacy', 'applied'), detail='formato anterior')]
        for block in cases:
            with self.subTest(status=block['status'], hooks=block['hooks']):
                doc = example()
                doc['playerLevelCaps'] = block
                summary = level_caps_summary(validate_document(json.dumps(doc)))
                self.assertEqual((summary['state'], summary['status']), ('unavailable', block['status']))
                self.assertEqual((summary['stages'], summary['checkpoints'], summary['tableSha256']), ([], [], None))
                self.assertTrue(summary['reason'])
                self.assertEqual(summary['detail'], block.get('detail'))

    def test_future_block_version_is_ignored_and_the_document_stays_valid(self):
        doc = example()
        doc['playerLevelCaps'] = {'version': 2, 'anything': {'new': True}}
        parsed = validate_document(json.dumps(doc))
        summary = level_caps_summary(parsed)
        self.assertEqual((summary['state'], summary['stages']), ('ignored', []))
        self.assertIn('versión 2', summary['reason'])
        self.assertEqual(parsed['playerLevelCaps'], {'version': 2, 'anything': {'new': True}})
        self.assertEqual(len(parsed['species']), 2)

    def test_malformed_or_inconsistent_blocks_are_ignored_without_rejecting_the_document(self):
        def edit(change):
            doc = example()
            change(doc['playerLevelCaps'])
            return doc
        duplicated = lambda b: b['checkpoints'][1].update(condition=copy.deepcopy(b['checkpoints'][0]['condition']))
        cases = {
            'not an object': lambda d: d.update(playerLevelCaps=[1]),
            'version as bool': lambda d: d['playerLevelCaps'].update(version=True),
            'version zero': lambda d: d['playerLevelCaps'].update(version=0),
            'unknown field': lambda d: d['playerLevelCaps'].update(current=1),
            'unknown status': lambda d: d['playerLevelCaps'].update(status='active'),
            'hooks do not match status': lambda d: d['playerLevelCaps']['hooks'].update(codeBin='stock'),
            'missing hook': lambda d: d['playerLevelCaps']['hooks'].pop('codeBin'),
            'wrong evaluation': lambda d: d['playerLevelCaps'].update(evaluation='any'),
            'wrong enforcement': lambda d: d['playerLevelCaps'].update(enforcement=['exp-gain']),
            'ceiling below 100': lambda d: d['playerLevelCaps'].update(ceiling=90),
            'no source': lambda d: d['playerLevelCaps'].pop('source'),
            'wrong scope': lambda d: d['playerLevelCaps']['source'].update(scope='personal'),
            'lowercase hash': lambda d: d['playerLevelCaps']['source'].update(tableSha256=d['playerLevelCaps']['source']['tableSha256'].lower()),
            'stale table hash': lambda d: d['playerLevelCaps']['source'].update(tableSha256='0' * 64),
            'no checkpoints': lambda d: d['playerLevelCaps'].update(checkpoints=[]),
            'order gap': lambda d: d['playerLevelCaps']['checkpoints'][2].update(order=7),
            'decreasing cap': lambda d: with_points(d, [(20, flag(1)), (10, flag(2))]),
            'duplicate condition': lambda d: duplicated(d['playerLevelCaps']),
            'cap 101': lambda d: with_points(d, [(101, flag(1))]),
            'cap as text': lambda d: d['playerLevelCaps']['checkpoints'][0].update(cap='15'),
            'flag byte out of range': lambda d: with_points(d, [(10, flag(620))]),
            'mask zero': lambda d: with_points(d, [(10, flag(1, 0))]),
            'work minimum zero': lambda d: with_points(d, [(10, {'kind': 'event-work-at-least', 'index': 1, 'minimum': 0})]),
            'unknown condition kind': lambda d: d['playerLevelCaps']['checkpoints'][0]['condition'].update(kind='badge'),
            'extra condition field': lambda d: d['playerLevelCaps']['checkpoints'][0]['condition'].update(index=1),
            'label without source': lambda d: d['playerLevelCaps']['checkpoints'][0].pop('labelSource'),
            'label of 61 characters': lambda d: d['playerLevelCaps']['checkpoints'][0].update(label='x' * 61),
            'label with control character': lambda d: d['playerLevelCaps']['checkpoints'][0].update(label='a\nb'),
            'label from another source': lambda d: d['playerLevelCaps']['checkpoints'][0].update(labelSource='game-text'),
            'stage field in checkpoint': lambda d: d['playerLevelCaps']['checkpoints'][0].update(id='a'),
            'more than 128 points': lambda d: with_points(d, [(50, flag(i // 8, 1 << (i % 8))) for i in range(129)]),
            'list in a status that is not installed': lambda d: d['playerLevelCaps'].update(status='inconsistent', hooks={'battleCro': 'applied', 'codeBin': 'stock'}),
            'table hash in a status that is not installed': lambda d: d.update(playerLevelCaps={
                **not_installed('not-detected', ('stock', 'stock')),
                'source': {'fingerprintAlgorithm': 'SHA-256', 'scope': 'battle.cro,code.bin', 'fingerprint': 'B' * 64, 'tableSha256': 'C' * 64}}),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                doc = example()
                change(doc)
                parsed = validate_document(json.dumps(doc))  # the rest of the DGD is still accepted
                summary = level_caps_summary(parsed)
                self.assertEqual((summary['state'], summary['stages'], summary['checkpoints']), ('ignored', [], []), name)
                self.assertIn('se ignoran', summary['reason'])
                with self.assertRaises((ValueError, TypeError, KeyError, AttributeError)):
                    validated_level_caps_block(doc['playerLevelCaps'])

    def test_more_than_64_points_is_rejected_whole_and_64_is_accepted(self):
        points = lambda count: [(min(100, 10 + i), flag(i)) for i in range(count)]
        full = level_caps_summary(validate_document(json.dumps(with_points(example(), points(MAX_STAGES)))))
        self.assertEqual((full['state'], len(full['stages'])), ('proposal', 64))
        over = level_caps_summary(validate_document(json.dumps(with_points(example(), points(MAX_STAGES + 1)))))
        self.assertEqual((over['state'], over['stages'], over['count']), ('rejected', [], 65))
        self.assertIn('no se recorta', over['reason'].lower())

    def test_document_without_block_and_tracker_1_4_0_data_are_unchanged(self):
        raw = ORIGINAL.read_text(encoding='utf-8')
        parsed = validate_document(raw)
        self.assertEqual(level_caps_summary(parsed)['state'], 'absent')
        with tempfile.TemporaryDirectory() as folder:
            # A file stored by Tracker 1.4.0 (which kept the block verbatim) opens as a proposal.
            path = Path(folder) / 'definitive-game-data.json'
            path.write_text(json.dumps(example('ultra-moon'), ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            manager = GameDataManager(path)
            self.assertIsNone(manager.error)
            self.assertEqual(manager.status(MOON)['levelCaps']['state'], 'proposal')
            self.assertIsNone(manager.status(SUN)['levelCaps'], 'inactive for another game')
            self.assertEqual(manager.species(1, 0, MOON)['baseStats']['hp'], 123)


class ProposalServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def service(self, name='run-a', doc=None, game=MOON):
        service = TrackerService(self.root / name / 'state.json')
        if doc is not False:
            self.load(service, doc if doc is not None else example('ultra-moon'), game)
        return service

    @staticmethod
    def load(service, doc, game=MOON):
        preview = service.preview_game_data(json.dumps(doc), game)
        service.apply_game_data(preview['previewToken'], game, True)

    @staticmethod
    def command(service, action='level_caps_accept_proposal', **extra):
        state = service.snapshot()
        block = state['game_data']['levelCaps'] or {}
        base = {'action': action, 'game': state['game'], 'dataFingerprint': state['game_data']['fingerprint'],
                'capsFingerprint': block.get('fingerprint'), 'tableSha256': block.get('tableSha256')}
        if action == 'level_caps_accept_proposal':
            base.update(finalStage=False, replace=False, listRevision=state['level_caps']['revision'])
        return {**base, **extra}

    def source_path(self, name='run-a', suffix=''):
        return self.root / name / f'state{suffix}-level-caps-source.json'

    def test_importing_data_never_changes_the_caps_of_the_run(self):
        service = self.service(doc=False)
        service.handle_command({'action': 'level_caps_set', 'stages': [{'name': 'Mi etapa', 'cap': 30}]})
        own = service.snapshot()['level_caps']
        service.handle_command({'action': 'level_caps_current', 'stage': own['stages'][0]['id']})
        before = service.snapshot()['level_caps']
        self.load(service, example('ultra-moon'))
        state = service.snapshot()
        self.assertEqual(state['game_data']['levelCaps']['state'], 'proposal')
        self.assertEqual(state['level_caps'], before, 'the proposal is not applied on its own')
        self.assertEqual(state['level_caps_source'], {'accepted': None, 'dismissed': None, 'error': None, 'matchesCurrent': False})
        self.assertFalse(self.source_path().exists())

    def test_accept_into_an_empty_run_saves_stages_without_a_current_one(self):
        service = self.service()
        service.handle_command({'action': 'level_caps_show', 'show': False})
        service.handle_command(self.command(service))
        state = service.snapshot()
        self.assertNotIn('last_command_error', state)
        caps = state['level_caps']
        self.assertEqual([(s['name'], s['cap']) for s in caps['stages']][:2],
                         [('Clear Normal Trial - Ilima (1dom)', 15), ('Defeat Kahuna Hala', 20)])
        self.assertEqual((caps['total'], caps['current'], caps['current_cap'], caps['show']), (6, None, None, False))
        accepted = state['level_caps_source']['accepted']
        block = state['game_data']['levelCaps']
        self.assertEqual((accepted['tableSha256'], accepted['capsFingerprint'], accepted['dataFingerprint']),
                         (block['tableSha256'], block['fingerprint'], state['game_data']['fingerprint']))
        self.assertEqual((accepted['checkpoints'], accepted['finalStage'], accepted['game'], accepted['source']),
                         (6, False, MOON, 'definitive-game-data'))
        self.assertTrue(state['level_caps_source']['matchesCurrent'])
        # The provenance lives in its own file; the level_caps block keeps its version 1 shape.
        stored = json.loads((self.root / 'run-a' / 'state-progress.json').read_text(encoding='utf-8'))['level_caps']
        self.assertEqual(set(stored), {'version', 'stages', 'current', 'show', 'updated_at', 'removed_current'})
        self.assertEqual(stored['version'], 1)
        self.assertEqual(set(stored['stages'][0]), {'id', 'name', 'cap'})
        record = json.loads(self.source_path().read_text(encoding='utf-8'))
        self.assertEqual((record['format'], record['version']), (SOURCE_FORMAT, 1))
        self.assertNotIn(str(self.root), self.source_path().read_text(encoding='utf-8'))

    def test_final_level_100_stage_is_optional_and_off_unless_requested(self):
        service = self.service()
        service.handle_command(self.command(service, finalStage=True))
        caps = service.snapshot()['level_caps']
        self.assertEqual((caps['total'], caps['stages'][-1]['name'], caps['stages'][-1]['cap'], caps['current']),
                         (7, FINAL_STAGE_NAME, 100, None))
        self.assertTrue(service.snapshot()['level_caps_source']['accepted']['finalStage'])
        for bad in (None, 1, 'true'):
            with self.subTest(finalStage=bad), self.assertRaises(ValueError):
                service.validate_level_caps(self.command(service, finalStage=bad, replace=True))
        with self.assertRaises(ValueError):
            command = self.command(service, replace=True)
            del command['finalStage']
            service.validate_level_caps(command)

    def test_replacing_existing_stages_needs_explicit_confirmation(self):
        service = self.service()
        service.handle_command({'action': 'level_caps_set', 'stages': [{'name': 'Gimnasio 1', 'cap': 14}, {'name': 'Gimnasio 2', 'cap': 20}]})
        own = service.snapshot()['level_caps']
        service.handle_command({'action': 'level_caps_current', 'stage': own['stages'][1]['id']})
        before = service.snapshot()['level_caps']
        with self.assertRaisesRegex(ValueError, 'Confirma'):
            service.validate_level_caps(self.command(service))
        service.handle_command(self.command(service))  # the worker refuses it too
        state = service.snapshot()
        self.assertEqual(state['level_caps'], before)
        self.assertIn('Confirma', state['last_command_error']['message'])
        self.assertIsNone(state['level_caps_source']['accepted'])
        service.handle_command(self.command(service, replace=True))
        caps = service.snapshot()['level_caps']
        self.assertEqual((caps['total'], caps['current'], caps['current_cap']), (6, None, None))
        self.assertEqual(caps['removed_current']['name'], 'Gimnasio 2', 'the previous current stage is only reported')
        self.assertTrue({s['id'] for s in caps['stages']}.isdisjoint({s['id'] for s in before['stages']}))

    def test_stale_confirmations_are_refused_and_change_nothing(self):
        service = self.service()
        good = self.command(service)
        stale = [({'game': SUN}, 'ya no es la vigente'), ({'dataFingerprint': 'F' * 64}, 'ya no es la vigente'),
                 ({'capsFingerprint': 'F' * 64}, 'ya no es la vigente'), ({'tableSha256': 'F' * 64}, 'ya no es la vigente'),
                 ({'listRevision': '0' * 16}, 'cambiaron mientras'), ({'listRevision': None}, 'cambiaron mientras')]
        for change, message in stale:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                service.validate_level_caps({**good, **change})
        # The list changes after the review was opened.
        service.handle_command({'action': 'level_caps_set', 'stages': [{'name': 'Nueva', 'cap': 9}]})
        service.handle_command({**good, 'replace': True})
        state = service.snapshot()
        self.assertEqual([s['name'] for s in state['level_caps']['stages']], ['Nueva'])
        self.assertIn('cambiaron mientras', state['last_command_error']['message'])
        # The imported data is replaced by another file with a different table.
        reviewed = self.command(service, replace=True)
        self.load(service, with_points(example('ultra-moon'), [(30, flag(5)), (40, flag(6))]))
        service.handle_command(reviewed)
        state = service.snapshot()
        self.assertEqual([s['name'] for s in state['level_caps']['stages']], ['Nueva'])
        self.assertIn('ya no es la vigente', state['last_command_error']['message'])
        self.assertIsNone(state['level_caps_source']['accepted'])
        # Withdrawn data: nothing left to accept.
        service.remove_game_data()
        with self.assertRaisesRegex(ValueError, 'No hay una propuesta'):
            service.validate_level_caps(reviewed)

    def test_only_installed_blocks_can_be_accepted(self):
        for block in (not_installed('not-detected', ('stock', 'stock')), not_installed('legacy-format', ('applied-legacy', 'stock')),
                      not_installed('inconsistent', ('stock', 'applied')), {'version': 2}):
            with self.subTest(block=block):
                doc = example('ultra-moon')
                doc['playerLevelCaps'] = block
                service = self.service('run-' + str(block.get('status')), doc)
                self.assertNotEqual(service.snapshot()['game_data']['levelCaps']['state'], 'proposal')
                with self.assertRaisesRegex(ValueError, 'No hay una propuesta'):
                    service.validate_level_caps(self.command(service, finalStage=False, replace=True))
                self.assertEqual(service.snapshot()['level_caps']['total'], 0)

    def test_more_than_64_points_cannot_be_accepted_or_truncated(self):
        doc = with_points(example('ultra-moon'), [(min(100, 10 + i), flag(i)) for i in range(65)])
        service = self.service(doc=doc)
        self.assertEqual(service.snapshot()['game_data']['levelCaps']['state'], 'rejected')
        with self.assertRaisesRegex(ValueError, 'No hay una propuesta'):
            service.validate_level_caps(self.command(service))
        self.assertEqual(service.snapshot()['level_caps']['total'], 0)
        # 64 points fit, but not together with the optional final stage.
        full = self.service('run-64', with_points(example('ultra-moon'), [(min(100, 10 + i), flag(i)) for i in range(64)]))
        with self.assertRaisesRegex(ValueError, 'No se recorta'):
            full.validate_level_caps(self.command(full, finalStage=True))
        full.handle_command(self.command(full))
        self.assertEqual(full.snapshot()['level_caps']['total'], 64)

    def test_dismiss_keeps_the_caps_and_can_be_undone(self):
        service = self.service()
        service.handle_command({'action': 'level_caps_set', 'stages': [{'name': 'Mía', 'cap': 12}]})
        before = service.snapshot()['level_caps']
        service.handle_command(self.command(service, 'level_caps_dismiss_proposal', dismissed=True))
        state = service.snapshot()
        self.assertEqual(state['level_caps'], before)
        self.assertEqual(state['level_caps_source']['dismissed']['tableSha256'], state['game_data']['levelCaps']['tableSha256'])
        self.assertTrue(self.source_path().exists())
        reopened = TrackerService(self.root / 'run-a' / 'state.json')
        self.assertIsNotNone(reopened.snapshot()['level_caps_source']['dismissed'])
        reopened.handle_command(self.command(reopened, 'level_caps_dismiss_proposal', dismissed=False))
        self.assertIsNone(reopened.snapshot()['level_caps_source']['dismissed'])
        self.assertFalse(self.source_path().exists(), 'an empty record leaves no file')
        with self.assertRaises(ValueError):
            reopened.validate_level_caps(self.command(reopened, 'level_caps_dismiss_proposal', dismissed='yes'))
        with self.assertRaisesRegex(ValueError, 'ya no es la vigente'):
            reopened.validate_level_caps(self.command(reopened, 'level_caps_dismiss_proposal', dismissed=True, tableSha256='F' * 64))
        # Accepting later clears the dismissal.
        reopened.handle_command(self.command(reopened, 'level_caps_dismiss_proposal', dismissed=True))
        reopened.handle_command(self.command(reopened, replace=True))
        source = reopened.snapshot()['level_caps_source']
        self.assertEqual((source['dismissed'], source['accepted']['checkpoints']), (None, 6))

    def test_accepted_caps_survive_reopening_editing_and_withdrawing_the_data(self):
        service = self.service()
        service.handle_command(self.command(service))
        accepted = service.snapshot()['level_caps']['stages']
        reopened = TrackerService(self.root / 'run-a' / 'state.json')
        state = reopened.snapshot()
        self.assertEqual(state['level_caps']['stages'], accepted)
        self.assertTrue(state['level_caps_source']['matchesCurrent'])
        self.assertEqual(state['game_data']['levelCaps']['state'], 'proposal')
        # Editing by hand keeps the record and reports that the list is no longer the proposal.
        edited = copy.deepcopy(accepted)
        edited[0]['cap'] = 16
        reopened.handle_command({'action': 'level_caps_set', 'stages': edited})
        source = reopened.snapshot()['level_caps_source']
        self.assertFalse(source['matchesCurrent'])
        self.assertEqual(source['accepted']['checkpoints'], 6)
        # Withdrawing the imported data removes neither the stages nor the record.
        reopened.remove_game_data()
        state = reopened.snapshot()
        self.assertFalse(state['game_data']['loaded'])
        self.assertIsNone(state['game_data']['levelCaps'])
        self.assertEqual([s['cap'] for s in state['level_caps']['stages']], [16, 20, 45, 50, 60, 70])
        self.assertEqual(state['level_caps_source']['accepted']['checkpoints'], 6)
        self.assertTrue(self.source_path().exists())
        again = TrackerService(self.root / 'run-a' / 'state.json').snapshot()
        self.assertEqual((again['level_caps']['total'], again['level_caps_source']['accepted']['checkpoints']), (6, 6))

    def test_runs_and_games_are_isolated(self):
        run_a, run_b = self.service('run-a'), self.service('run-b', doc=False)
        run_a.handle_command(self.command(run_a))
        self.assertEqual(run_b.snapshot()['level_caps']['total'], 0)
        self.assertIsNone(run_b.snapshot()['game_data']['levelCaps'])
        self.assertIsNone(run_b.snapshot()['level_caps_source']['accepted'])
        self.assertFalse(self.source_path('run-b').exists())
        # A confirmation reviewed in run A is not valid in run B, even after importing other data there.
        reviewed = self.command(run_a, replace=True)
        other = example('ultra-moon')
        other['source']['fingerprint'] = 'C' * 64
        self.load(run_b, other)
        with self.assertRaisesRegex(ValueError, 'ya no es la vigente'):
            run_b.validate_level_caps({**reviewed, 'listRevision': run_b.snapshot()['level_caps']['revision']})
        # Another game of the same run has its own stages and its own record.
        sun = TrackerService(self.root / 'run-a' / 'state.json')
        sun.profile = PROFILES[SUN]
        suffix = TrackerService.progress_suffix(SUN)
        sun.open_progress(suffix)
        sun.update(game=SUN, stale=True)
        sun._refresh_game_data()
        state = sun.snapshot()
        self.assertEqual((state['level_caps']['total'], state['level_caps_source']['accepted']), (0, None))
        self.assertIsNone(state['game_data']['levelCaps'], 'the Ultra Moon import is inactive for Ultra Sun')
        with self.assertRaisesRegex(ValueError, 'No hay una propuesta'):
            sun.validate_level_caps({**reviewed, 'game': SUN, 'listRevision': state['level_caps']['revision']})
        self.assertFalse(self.source_path('run-a', suffix).exists())
        self.assertTrue(self.source_path('run-a').exists())

    def test_damaged_or_newer_provenance_never_blocks_the_run(self):
        service = self.service()
        service.handle_command(self.command(service))
        stages = service.snapshot()['level_caps']['stages']
        path = self.source_path()
        path.write_text('{broken', encoding='utf-8')
        damaged = TrackerService(self.root / 'run-a' / 'state.json').snapshot()
        self.assertEqual(damaged['level_caps']['stages'], stages)
        self.assertIsNone(damaged['level_caps_source']['accepted'])
        self.assertIn('No se pudo leer la procedencia', damaged['level_caps_source']['error'])
        newer = json.dumps({'format': SOURCE_FORMAT, 'version': 2, 'accepted': {'anything': 1}})
        path.write_text(newer, encoding='utf-8')
        future = TrackerService(self.root / 'run-a' / 'state.json')
        self.assertIn('versión más nueva', future.snapshot()['level_caps_source']['error'])
        with self.assertRaisesRegex(ValueError, 'versión más nueva'):
            future.validate_level_caps(self.command(future, replace=True))
        future.handle_command(self.command(future, replace=True))
        self.assertEqual(future.snapshot()['level_caps']['stages'], stages)
        self.assertEqual(path.read_text(encoding='utf-8'), newer, 'kept untouched')

    def test_provenance_write_failure_is_reported_and_stages_are_not_lost(self):
        service = self.service()
        with patch.object(LevelCapsSource, '_save', side_effect=OSError('disco lleno')):
            service.handle_command(self.command(service))
        state = service.snapshot()
        self.assertEqual(state['level_caps']['total'], 6)
        self.assertIn('no se pudo guardar su procedencia', state['last_command_error']['message'])
        self.assertIsNone(state['level_caps_source']['accepted'])
        self.assertFalse(self.source_path().exists())

    def test_existing_flows_are_untouched(self):
        service = self.service()
        state = service.snapshot()
        self.assertEqual(level_caps_view({})['revision'], stages_revision([]))
        service.handle_command({'action': 'level_caps_set', 'stages': [{'name': 'A', 'cap': 10}, {'name': 'B', 'cap': 20}]})
        stages = service.snapshot()['level_caps']['stages']
        self.assertNotEqual(service.snapshot()['level_caps']['revision'], state['level_caps']['revision'])
        service.handle_command({'action': 'level_caps_current', 'stage': stages[1]['id']})
        self.assertEqual(service.snapshot()['level_caps']['current_cap'], 20)
        self.assertEqual(service.level_caps_export()['stages'], [{'name': 'A', 'cap': 10}, {'name': 'B', 'cap': 20}])
        self.assertEqual(set(service.session_export()), {'schema_version', 'exported_at', 'game', 'party', 'boxes', 'progress',
                                                         'selected_box', 'box_verified'})
        self.assertFalse(self.source_path().exists())


class ProposalApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = TrackerService(Path(self.temp.name) / 'state.json')
        ProposalServiceTests.load(self.service, example('ultra-moon'))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service, 'test-token'))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def post(self, payload):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.request('POST', '/api/command', body=json.dumps(payload),
                               headers={'Content-Type': 'application/json', 'X-Tracker-Token': 'test-token'})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def drain(self):
        while not self.service.commands.empty():
            self.service.handle_command(self.service.commands.get())

    def test_http_validates_before_queueing_and_the_worker_applies(self):
        command = ProposalServiceTests.command(self.service)
        status, body = self.post({**command, 'tableSha256': 'F' * 64})
        self.assertEqual(status, 400)
        self.assertIn('ya no es la vigente', body['error'])
        self.assertTrue(self.service.commands.empty())
        status, _ = self.post({'action': 'level_caps_accept_proposal'})
        self.assertEqual(status, 400)
        status, _ = self.post(command)
        self.assertEqual(status, 202)
        self.assertEqual(self.service.snapshot()['level_caps']['total'], 0, 'nothing changes before the worker runs')
        self.drain()
        state = self.service.snapshot()
        self.assertEqual((state['level_caps']['total'], state['level_caps']['current']), (6, None))
        status, _ = self.post(ProposalServiceTests.command(self.service, 'level_caps_dismiss_proposal', dismissed=True))
        self.assertEqual(status, 202)
        self.drain()
        self.assertIsNotNone(self.service.snapshot()['level_caps_source']['dismissed'])

    def test_state_endpoint_exposes_the_proposal_and_its_provenance(self):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.request('GET', '/api/game-data')
            status = json.loads(connection.getresponse().read())
        finally:
            connection.close()
        self.assertEqual((status['levelCaps']['state'], status['levelCaps']['count']), ('proposal', 6))
        self.assertEqual(self.service.snapshot()['level_caps_source']['accepted'], None)


if __name__ == '__main__':
    unittest.main()
