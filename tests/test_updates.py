"""Aviso de nueva versión: sin red real, con un fetcher simulado."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tracker.updates import (API_URL, DISABLE_ENV, FALLBACK_URL, MAX_BYTES, UpdateChecker,
                             parse_release, parse_version)

RELEASE_URL = 'https://github.com/joanjuz/NuzlockeTracker/releases/tag/v1.1.0'


def release(tag='v1.1.0', url=RELEASE_URL, **extra):
    return json.dumps({'tag_name': tag, 'html_url': url, **extra}).encode()


class FakeFetcher:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.called = threading.Event()

    def __call__(self, url, timeout, max_bytes):
        self.calls.append((url, timeout, max_bytes))
        self.called.set()
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, BaseException):
            raise item
        return item


class ParseTests(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(parse_version('v1.2.3'), (1, 2, 3))
        self.assertEqual(parse_version('1.10.0'), (1, 10, 0))
        for bad in ('v1.2', '1.2.3-beta', 'latest', None, 123, 'v1.2.3.4'):
            self.assertIsNone(parse_version(bad), bad)

    def test_release_validation(self):
        self.assertEqual(parse_release(release()), {'latest': '1.1.0', 'url': RELEASE_URL})
        for raw in (b'[]', b'"v1.1.0"', b'no json', release(tag='nightly'), release(tag=None),
                    b'x' * (MAX_BYTES + 1), None):
            with self.subTest(raw=raw[:20] if raw else raw), self.assertRaises(ValueError):
                parse_release(raw)

    def test_foreign_or_odd_links_fall_back_to_the_releases_page(self):
        for url in ('https://evil.example/releases/', 'http://github.com/joanjuz/NuzlockeTracker/releases/x',
                    'https://github.com/other/NuzlockeTracker/releases/tag/v9.0.0',
                    'https://github.com/joanjuz/NuzlockeTracker/releases/ x', None, 42):
            with self.subTest(url=url):
                self.assertEqual(parse_release(release(url=url))['url'], FALLBACK_URL)


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / 'runtime' / 'update-check.json'

    def checker(self, fetcher, **options):
        options.setdefault('env', {})
        options.setdefault('current', '1.0.0')
        return UpdateChecker(self.cache, fetcher=fetcher, **options)

    def test_newer_release_is_reported_and_cached(self):
        fetcher = FakeFetcher(release())
        checker = self.checker(fetcher)
        self.assertTrue(checker.check_now())
        self.assertEqual(fetcher.calls, [(API_URL, 8.0, MAX_BYTES)])
        status = checker.status()
        self.assertEqual({k: status[k] for k in ('current', 'latest', 'update_available', 'url')},
                         {'current': '1.0.0', 'latest': '1.1.0', 'update_available': True, 'url': RELEASE_URL})
        self.assertRegex(status['checked_at'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$')
        # A new process reads the cache without touching the network.
        offline = self.checker(FakeFetcher(OSError('sin red')), enabled=False)
        self.assertEqual(offline.status(), status)

    def test_same_or_older_release_is_not_an_update(self):
        for tag in ('v1.0.0', 'v0.25.0'):
            with self.subTest(tag=tag):
                checker = self.checker(FakeFetcher(release(tag=tag)))
                checker.check_now()
                self.assertFalse(checker.status()['update_available'])
        upgraded = self.checker(FakeFetcher(release()), current='1.1.0')
        upgraded.check_now()
        self.assertFalse(upgraded.status()['update_available'])

    def test_failures_never_raise_and_keep_the_previous_result(self):
        fetcher = FakeFetcher(release(), OSError('timeout'), b'{"tag_name": 5}', RuntimeError('raro'))
        checker = self.checker(fetcher)
        self.assertTrue(checker.check_now())
        before = checker.status()
        for _ in range(3):
            self.assertFalse(checker.check_now())
        self.assertEqual(checker.status(), before)

    def test_empty_status_before_any_check(self):
        checker = self.checker(FakeFetcher(OSError('x')))
        self.assertEqual(checker.status(), {'current': '1.0.0', 'latest': None, 'update_available': False,
                                            'url': FALLBACK_URL, 'checked_at': None})

    def test_corrupt_or_foreign_cache_is_ignored_or_sanitised(self):
        self.cache.parent.mkdir(parents=True)
        self.cache.write_text('{no json', encoding='utf-8')
        self.assertIsNone(self.checker(FakeFetcher(b'')).status()['latest'])
        self.cache.write_text(json.dumps({'latest': '2.0.0', 'url': 'https://evil.example/',
                                          'checked_at': 'x' * 100}), encoding='utf-8')
        status = self.checker(FakeFetcher(b'')).status()
        self.assertEqual((status['latest'], status['url'], status['checked_at']), ('2.0.0', FALLBACK_URL, None))

    def test_environment_variable_disables_network(self):
        fetcher = FakeFetcher(release())
        checker = self.checker(fetcher, env={DISABLE_ENV: '1'}, initial_delay=0)
        self.assertFalse(checker.enabled)
        checker.start()
        self.assertFalse(checker.check_now())
        checker.close()
        self.assertEqual(fetcher.calls, [])

    def test_thread_checks_after_delay_and_stops_on_close(self):
        fetcher = FakeFetcher(release())
        checker = self.checker(fetcher, initial_delay=0.01, interval=3600)
        checker.start()
        checker.start()  # idempotent: one thread per process
        self.assertTrue(fetcher.called.wait(5))
        thread = checker._thread
        checker.close()
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(fetcher.calls), 1)
        self.assertTrue(checker.status()['update_available'])

    def test_unwritable_cache_does_not_break_the_check(self):
        checker = self.checker(FakeFetcher(release()))
        with patch('pathlib.Path.write_text', side_effect=OSError('solo lectura')):
            self.assertTrue(checker.check_now())
        self.assertTrue(checker.status()['update_available'])
        self.assertFalse(self.cache.exists())


class BackendWiringTests(unittest.TestCase):
    def test_checker_survives_profile_switch_and_stops_on_close(self):
        from desktop import LocalBackend
        from tracker.layout_export import BLANK_PNG, PartyLayoutExporter
        with tempfile.TemporaryDirectory() as temp, \
                patch('desktop.PartyLayoutExporter', side_effect=lambda *a, **k:
                      PartyLayoutExporter(*a, downloader=lambda _: BLANK_PNG, **k)), \
                patch('desktop.CompanionSync.start'):
            backend = LocalBackend(Path(temp) / 'runtime', 'principal').start()
            try:
                checker = backend.updates
                self.assertFalse(checker.enabled)  # tests and smoke test never reach GitHub
                self.assertEqual(checker.cache_path, Path(temp) / 'runtime' / 'update-check.json')
                ident = backend.create_profile('Otra partida')['created']
                backend.switch_profile(ident)
                self.assertIs(backend.updates, checker)
                self.assertIs(backend.server.RequestHandlerClass.ctx.updates, checker)
            finally:
                with patch.object(checker, 'close', wraps=checker.close) as close:
                    backend.close()
                close.assert_called_once_with()

    def test_enabled_backend_starts_one_checker(self):
        from desktop import LocalBackend
        with tempfile.TemporaryDirectory() as temp, patch('desktop.UpdateChecker') as factory:
            backend = LocalBackend(Path(temp) / 'runtime', 'principal', check_updates=True)
        factory.assert_called_once()
        self.assertTrue(factory.call_args.kwargs['enabled'])
        self.assertIs(backend.updates, factory.return_value)


if __name__ == '__main__':
    unittest.main()
