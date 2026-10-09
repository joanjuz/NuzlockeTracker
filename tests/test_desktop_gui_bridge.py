"""Regression: avoid recursive pywebview js_api exposure hanging the GUI."""
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from desktop import create_desktop_window


class GuiBridgeTests(unittest.TestCase):
    def test_js_bridge_exposes_only_one_function_without_object_graph(self):
        window = Mock()
        window.expose = Mock()
        webview = SimpleNamespace(create_window=Mock(return_value=window))
        backend = SimpleNamespace(service=object(), url='http://127.0.0.1:12345/')
        with patch('desktop.DesktopExportApi') as factory:
            export_api = factory.return_value
            created = create_desktop_window(backend, webview)
            self.assertIs(created, window)
            factory.assert_called_once_with(backend.service)
            args, kwargs = webview.create_window.call_args
            self.assertEqual(args[:2], ('Pokémon Tracker', backend.url))
            self.assertNotIn('js_api', kwargs,
                'Passing service/window-bearing objects into js_api hangs initialization')
            window.expose.assert_called_once()
            exposed = window.expose.call_args.args[0]
            self.assertTrue(inspect.isfunction(exposed))
            self.assertEqual(exposed.__name__, 'save_export')
            self.assertEqual(list(inspect.signature(exposed).parameters), ['kind'])
            export_api.save_export.return_value = {'saved': True, 'name': 'sesion.json'}
            self.assertEqual(exposed('session'), {'saved': True, 'name': 'sesion.json'})
            export_api.save_export.assert_called_once_with('session')
            self.assertIs(export_api.window, window)

    def test_death_counter_is_right_of_mini_team_left_of_equipo_tab(self):
        html = (Path(__file__).resolve().parent.parent / 'web' / 'index.html').read_text(encoding='utf-8')
        mini = html.index('id="mini-team"')
        deaths = html.index('id="death-counter"')
        nav = html.index('<nav aria-label="Secciones del tracker">')
        equipo = html.index('data-tab="party"')
        self.assertTrue(mini < deaths < nav < equipo)
        self.assertEqual(html.count('id="death-counter"'), 1)


if __name__ == '__main__':
    unittest.main()
