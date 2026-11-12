"""Reusable stage lists: shareable export, native save, and import through the existing atomic command."""
import copy
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tracker.desktop_export import DesktopExportApi, export_payload
from tracker.progress import (MAX_STAGES, STAGE_LIST_FORMAT, STAGE_LIST_VERSION, RunProgress,
                              level_caps_view, stage_list_export)
from tracker.service import TrackerService

from test_level_caps import mon, stages


class FileWindow:
    def __init__(self, selected):
        self.selected = selected
        self.calls = []

    def create_file_dialog(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.selected


FAKE_WEBVIEW = types.SimpleNamespace(FileDialog=types.SimpleNamespace(SAVE=30))


class StageListTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def service(self, name='run-a'):
        return TrackerService(self.root / name / 'state.json')

    def private_run(self, name='run-a'):
        """A run full of data that must never reach a shared file."""
        service = self.service(name)
        service.handle({'action': 'level_caps_set', 'stages': stages(14, 12, 30, names=['Gimnasio 1', 'Cueva', 'Liga'])})
        ids = [s['id'] for s in service.snapshot()['level_caps']['stages']]
        service.handle({'action': 'level_caps_current', 'stage': ids[1]})
        service.handle({'action': 'level_caps_show', 'show': False})
        service.progress.mark_dead(mon(ec=77))
        service.progress.set_miss('10', True)
        return service, ids

    # --- export -------------------------------------------------------------------------------
    def test_export_has_only_format_names_caps_and_order(self):
        service, ids = self.private_run()
        document = service.level_caps_export()
        self.assertEqual(document, {
            'format': STAGE_LIST_FORMAT, 'version': STAGE_LIST_VERSION,
            'stages': [{'name': 'Gimnasio 1', 'cap': 14}, {'name': 'Cueva', 'cap': 12}, {'name': 'Liga', 'cap': 30}]})
        self.assertEqual((STAGE_LIST_FORMAT, STAGE_LIST_VERSION), ('progressive-tracker-stage-list', 1))
        text = json.dumps(document)
        for private in (*ids, 'current', 'show', 'updated_at', 'removed', 'death', 'encounter', 'token',
                        'companion', 'profile', 'path', str(self.root), 'run-a', '33:77'):
            self.assertNotIn(private, text)

    def test_export_reads_only_the_saved_list_and_changes_nothing(self):
        service, _ = self.private_run()
        before = copy.deepcopy(service.progress.data)
        service.level_caps_export()
        self.assertEqual(service.progress.data, before)
        # The result is a copy: editing it never edits the run.
        document = service.level_caps_export()
        document['stages'][0]['name'] = 'Otro'
        self.assertEqual(service.progress.data['level_caps']['stages'][0]['name'], 'Gimnasio 1')

    def test_nothing_to_export_is_refused(self):
        service = self.service()
        with self.assertRaises(ValueError):
            service.level_caps_export()
        service.handle({'action': 'level_caps_set', 'stages': stages(10)})
        service.handle({'action': 'level_caps_set', 'stages': []})
        with self.assertRaises(ValueError):
            service.level_caps_export()
        with self.assertRaises(ValueError):
            stage_list_export({'status': 'unsupported', 'stages': []})
        newer = self.service('newer')
        newer.progress.data['level_caps'] = {'version': 9, 'stages': 'otra cosa'}
        with self.assertRaises(ValueError):
            newer.level_caps_export()

    def test_native_save_writes_only_the_chosen_file(self):
        service, _ = self.private_run()
        chosen = self.root / 'compartida.json'
        window = FileWindow((str(chosen),))
        api = DesktopExportApi(service, window)
        with patch.dict(sys.modules, {'webview': FAKE_WEBVIEW}):
            self.assertEqual(api.save_export('level_caps'), {'saved': True, 'name': 'compartida.json'})
            self.assertEqual(window.calls[0][1]['save_filename'], 'limites-de-nivel.json')
            self.assertEqual(window.calls[0][1]['file_types'], ('Archivo JSON (*.json)',))
            self.assertEqual(json.loads(chosen.read_text(encoding='utf-8')), service.level_caps_export())
            window.selected = None
            self.assertEqual(api.save_export('level_caps'), {'cancelled': True})
            # An empty run reports a clear error and writes nothing.
            empty = DesktopExportApi(self.service('vacia'), FileWindow((str(self.root / 'vacio.json'),)))
            result = empty.save_export('level_caps')
            self.assertIn('no tiene', result['error'])
            self.assertFalse((self.root / 'vacio.json').exists())
        self.assertEqual(export_payload(service, 'level_caps'), service.level_caps_export())
        with self.assertRaises(ValueError):
            export_payload(service, 'private')

    # --- import (the existing atomic command; the browser sends names and caps only) ----------------
    def import_list(self, service, document):
        service.handle({'action': 'level_caps_set', 'stages': copy.deepcopy(document['stages'])})
        return service.snapshot()['level_caps']

    def test_roundtrip_between_runs_creates_new_ids_and_no_current_stage(self):
        source, source_ids = self.private_run('run-a')
        document = json.loads(json.dumps(source.level_caps_export(), ensure_ascii=False))
        target = self.service('run-b')
        target.progress.mark_dead(mon(ec=5))
        deaths = copy.deepcopy(target.progress.data['deaths'])
        view = self.import_list(target, document)
        self.assertEqual([(s['name'], s['cap']) for s in view['stages']],
                         [('Gimnasio 1', 14), ('Cueva', 12), ('Liga', 30)], 'Nombres, límites y orden')
        self.assertEqual(len({s['id'] for s in view['stages']}), 3)
        self.assertTrue({s['id'] for s in view['stages']}.isdisjoint(source_ids), 'IDs nuevos')
        self.assertIsNone(view['current'], 'No se elige ninguna etapa vigente')
        self.assertTrue(view['show'], 'Una partida nueva conserva su opción de mostrar (por defecto)')
        self.assertEqual(view['decreasing'], [view['stages'][1]['id']], 'El límite decreciente se permite y se avisa')
        self.assertEqual(target.progress.data['deaths'], deaths, 'Muertes y encuentros no se tocan')
        # The source run is untouched by being exported and re-imported elsewhere.
        self.assertEqual([s['id'] for s in source.snapshot()['level_caps']['stages']], source_ids)
        self.assertEqual(source.snapshot()['level_caps']['current'], source_ids[1])
        # Exporting what was imported gives the same document: stable roundtrip.
        self.assertEqual(target.level_caps_export(), document)

    def test_replacing_keeps_show_and_clears_the_current_stage_without_picking_another(self):
        service, ids = self.private_run()
        self.assertEqual(service.snapshot()['level_caps']['current'], ids[1])
        view = self.import_list(service, {'stages': stages(40, 50, names=['Nueva A', 'Nueva B'])})
        self.assertEqual([s['name'] for s in view['stages']], ['Nueva A', 'Nueva B'], 'Se reemplaza la lista completa')
        self.assertIsNone(view['current'])
        self.assertFalse(view['show'], 'La opción show de la partida se mantiene')
        self.assertEqual(view['removed_current']['name'], 'Cueva', 'Se avisa de cuál era la etapa vigente')
        self.assertTrue({s['id'] for s in view['stages']}.isdisjoint(ids))

    def test_failed_import_keeps_the_previous_configuration(self):
        service, ids = self.private_run()
        before = copy.deepcopy(service.progress.data)
        too_many = [{'name': f'E{i}', 'cap': 10} for i in range(MAX_STAGES + 1)]
        for bad in (too_many, stages(0), stages(101), [{'name': '', 'cap': 5}], [{'name': 'x' * 61, 'cap': 5}],
                    [{'name': 'A', 'cap': 5, 'id': 'a b'}], [{'name': 'A', 'cap': True}], 'no es una lista'):
            with self.subTest(bad=str(bad)[:50]):
                service.handle_command({'action': 'level_caps_set', 'stages': bad})
                self.assertEqual(service.progress.data, before)
                self.assertEqual(service.snapshot()['last_command_error']['action'], 'level_caps_set')
        self.assertEqual([s['id'] for s in service.snapshot()['level_caps']['stages']], ids)

    def test_limits_of_the_model_are_respected_by_a_full_import(self):
        service = self.service()
        full = stages(*([1, 100] * (MAX_STAGES // 2)), names=['n' * 60] * MAX_STAGES)
        view = self.import_list(service, {'stages': full})
        self.assertEqual(view['total'], MAX_STAGES)
        self.assertEqual({s['cap'] for s in view['stages']}, {1, 100})
        self.assertEqual(service.level_caps_export()['stages'], full)

    def test_runs_and_games_stay_isolated_during_import_and_export(self):
        a, _ = self.private_run('run-a')
        b = self.service('run-b')
        self.import_list(b, a.level_caps_export())
        b.handle({'action': 'level_caps_set', 'stages': stages(99, names=['Solo B'])})
        self.assertEqual([s['name'] for s in a.snapshot()['level_caps']['stages']], ['Gimnasio 1', 'Cueva', 'Liga'])
        self.assertEqual(a.level_caps_export()['stages'][0], {'name': 'Gimnasio 1', 'cap': 14})
        # Another game of the same run keeps its own progress file.
        suffix = TrackerService.progress_suffix('Ultra Sun 1.0')
        sun = RunProgress(a.output.with_name(a.output.stem + suffix + '-progress.json'))
        self.assertNotEqual(sun.path, a.progress.path)
        self.assertEqual(level_caps_view(sun.data)['status'], 'none')
        sun.set_level_caps(stages(7, names=['Otro juego']))
        self.assertEqual([s['name'] for s in a.level_caps_export()['stages']], ['Gimnasio 1', 'Cueva', 'Liga'])


if __name__ == '__main__':
    unittest.main()
