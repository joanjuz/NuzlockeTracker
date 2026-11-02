import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from companion.snapshot import snapshot, viewer_state, FIELD_CHECKS, STRICT_FIELDS
from companion.sync import CompanionSync, validate_worker_url, fetch_json
from server import make_handler


def mon():
    return {'species_id':448,'species':'Lucario','nickname':'Goty','level':75,'hp':217,'max_hp':217,
            'moves':[1,2,3,4],'move_names':['A','B','C','D'],'iv':[31]*6,'ev':[0]*6,
            'encryption_constant':1234,'origin_version':33,'met_location_id':8,'met_location':'Ruta 1',
            'ability':'Foco Interno','item':'Restos','nature':'Firme','stats':{'ATQ':123},
            'checksum_valid': True, 'unsafe_internal_field':'NEVER_SEND', 'pid':9999}


def state(game='Ultra Sun 1.0'):
    return {'game':game,'connection':{'status':'connected'},'stale':False,'party':[mon()]+[None]*5,
            'boxes':{'1':[mon()]+[None]*29},'progress':{'deaths':{'33:1234':{'pokemon':mon(), 'recorded_at':'2026-01-01'}},
            'missed_routes':['10'],'revived_pending':['33:3']}, 'diagnostic':'NEVER_SEND','pid':999}


class Service:
    def __init__(self):self.current=state()
    def snapshot(self):return self.current


class CompanionTests(unittest.TestCase):
    def test_snapshot_excludes_unrelated_fields(self):
        result = snapshot(state())
        serialized = json.dumps(result)
        for word in ['NEVER_SEND','diagnostic','pid','checksum_valid','revived_pending']:
            self.assertNotIn(word, serialized)
        self.assertEqual(result['party'][0]['met_location'], 'Ruta 1')
        self.assertEqual(result['boxes']['1'][0]['nickname'], 'Goty')
        self.assertEqual(result['progress']['missed_routes'], ['10'])
        self.assertIn('33:1234', result['progress']['deaths'])
        self.assertEqual(result['progress']['death_count'],1)

    def test_soullink_reply_is_shared_without_rebroadcasting_private_fields(self):
        current = state()
        entry = current['progress']['deaths']['33:1234']
        entry['source'] = 'soullink-response'
        entry['private_token'] = 'LEAK_NEVER'
        shared = snapshot(current)
        saved = shared['progress']['deaths']['33:1234']
        self.assertEqual(saved['source'], 'soullink-response')
        self.assertNotIn('private_token', json.dumps(shared))
        self.assertEqual(viewer_state(shared)['progress']['deaths']['33:1234']['source'],
                         'soullink-response')
        entry['source'] = 'manual'
        self.assertNotIn('source', snapshot(current)['progress']['deaths']['33:1234'])
        entry['source'] = 'untrusted'
        self.assertNotIn('source', snapshot(current)['progress']['deaths']['33:1234'])

    def test_share_origin_categories_safe_and_visible_to_partner(self):
        local=state()
        local['progress']['origins']={'33:1234':'fossil'}
        shared=snapshot(local)
        self.assertEqual(shared['progress']['origins'],{'33:1234':'fossil'})
        self.assertEqual(viewer_state(shared)['progress']['origins']['33:1234'],'fossil')
        for origins in ({'33:1234':'invalid'}, {'../../secret':'gift'},
                        {'33:1234':None}, ['fossil']):
            with self.subTest(origins=origins),self.assertRaises(ValueError):
                local['progress']['origins']=origins
                snapshot(local)

    def test_traded_away_route_mark_reaches_partner_without_history(self):
        local=state()
        pokemon=mon()
        local['progress']['encounters']={'33:1234':pokemon}
        local['progress']['route_marks']={'33:1234':{
          'kind':'trade','pokemon':pokemon,'recorded_at':'2026-10-09',
          'private_token':'NEVER_SEND'}}
        shared=snapshot(local)
        self.assertNotIn('encounters',shared['progress'])
        self.assertNotIn('private_token',json.dumps(shared))
        mark=viewer_state(shared)['progress']['route_marks']['33:1234']
        self.assertEqual(mark['kind'],'trade')
        self.assertEqual(mark['pokemon']['nickname'],'Goty')
        self.assertEqual(mark['pokemon']['met_location_id'],8)
        local['progress']['route_marks']['33:1234']['kind']='unknown'
        with self.assertRaises(ValueError):
            snapshot(local)

    def test_share_route_trade_flag_but_not_full_scan_baseline(self):
        current=state()
        current['progress']['traded_routes']=['8']
        current['progress']['full_scan_baseline']={'33:1234':123456}
        result=snapshot(current)
        self.assertEqual(result['progress']['traded_routes'],['8'])
        self.assertNotIn('full_scan_baseline',result['progress'])
        self.assertEqual(viewer_state(result)['progress']['traded_routes'],['8'])
        current['progress']['traded_routes']=['../../private']
        with self.assertRaises(ValueError):snapshot(current)

    def test_viewer_can_render_last_session(self):
        old = snapshot(state('Ultra Moon 1.0'))
        view = viewer_state(old)
        self.assertTrue(view['stale'])
        self.assertEqual(view['game'],'Ultra Moon 1.0')
        self.assertEqual(view['progress']['deaths']['33:1234']['pokemon']['nickname'],'Goty')
        self.assertFalse(view['scan']['active'])

    def test_incomplete_snapshot_rejected(self):
        s=state();s['party']=[None]
        with self.assertRaises(ValueError):snapshot(s)
        s=state();s['stale']=True
        with self.assertRaises(ValueError):snapshot(s)

    def test_cloud_url_restrictions(self):
        self.assertEqual(validate_worker_url('https://example.account.workers.dev/'),'https://example.account.workers.dev')
        for url in ['http://evil.workers.dev','https://192.168.1.5','https://evil.com',
                    'https://evil.workers.dev/api','https://evil.workers.dev/?token=x',
                    'https://a.workers.dev@evil.com']:
            with self.assertRaises(ValueError):validate_worker_url(url)

    def test_http_client_uses_compatible_user_agent(self):
        """Regression: urllib default User-Agent got Cloudflare HTTP 403, while Mozilla/5.0 worked."""
        requests = []

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, size=None):
                return b'{"ok":true}'

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return Response()

        with patch('companion.sync.urlopen', side_effect=fake_urlopen):
            self.assertEqual(fetch_json('https://a.b.workers.dev/health'), {'ok': True})
            self.assertEqual(fetch_json('https://a.b.workers.dev/v1/pairs', 'POST',
                                        {'name': 'Sol', 'game': 'Ultra Sun 1.0'},
                                        setup_key='private-test-key'), {'ok': True})
        self.assertEqual(len(requests), 2)
        for req, timeout in requests:
            self.assertEqual(req.get_header('User-agent'), 'Mozilla/5.0')
            self.assertEqual(req.get_header('Accept'), 'application/json')
            self.assertEqual(timeout, 8)
        self.assertEqual(requests[0][0].get_method(), 'GET')
        self.assertEqual(requests[1][0].get_method(), 'POST')
        self.assertEqual(requests[1][0].get_header('X-setup-key'), 'private-test-key')

    def test_default_worker_and_full_invitation_link(self):
        calls=[]
        def fake_transport(url, method='GET', payload=None, token=None, setup_key=None):
            calls.append(url)
            if url.endswith('/v1/pairs/join'):
                return {'pair_id':'pair-two','token':'token-two'}
            return {'pair_id':'pair-one','token':'token-one','invite_code':'1234567890abcdef1234567890abcdef'}
        with tempfile.TemporaryDirectory() as root:
            first=CompanionSync(Service(),Path(root)/'runtime',fake_transport)
            s=first.perform('create',{'name':'Sol','game':'Ultra Sun 1.0','setup_key':'admin-secret-test-123'})
            self.assertEqual(s['default_worker_url'], 'https://pokemon-tracker-companion.pokemon-tracker.workers.dev')
            self.assertEqual(s['invite_link'],s['default_worker_url']+'/join#'+s['invite_code'])
            second=CompanionSync(Service(),Path(root)/'runtime'/'profiles'/'segundo-jugador',fake_transport)
            self.assertEqual(second.status()['default_worker_url'],s['default_worker_url'])
            joined=second.perform('join',{'name':'Luna','game':'Ultra Moon 1.0','invite_code':s['invite_link']})
            self.assertTrue(joined['configured'])
            self.assertEqual(calls[-1],s['default_worker_url']+'/v1/pairs/join')

    def test_scanning_coalesces_box_updates_but_not_hp(self):
        events=[]
        def fake_transport(url, method='GET', payload=None, token=None, setup_key=None):
            events.append(method)
            if url.endswith('/v1/pairs'):return {'pair_id':'p','token':'token','invite_code':'invitation123456789'}
            if url.endswith('/v1/partner'):return {'partner_joined':False,'partner':None}
            if url.endswith('/v1/state'):return {'ok':True}
            raise AssertionError(url)
        with tempfile.TemporaryDirectory() as directory:
            service=Service()
            sync=CompanionSync(service,directory,fake_transport)
            sync.perform('create',{'name':'Sol','game':'Ultra Sun 1.0','setup_key':'admin-secret-test-123'})
            sync.sync_once()
            def put_count():return events.count('PUT')
            self.assertEqual(put_count(),1)
            service.current['scan']={'active':True,'completed':1}
            service.current['boxes']['2']=[mon()]+[None]*29
            sync.sync_once()
            self.assertEqual(put_count(),1)
            service.current['party'][0]['hp']=100
            sync.sync_once()
            self.assertEqual(put_count(),2)
            service.current['boxes']['3']=[mon()]+[None]*29
            sync.sync_once()
            self.assertEqual(put_count(),2)
            service.current['scan']={'active':False,'completed':32}
            sync.sync_once()
            self.assertEqual(put_count(),3)

    def test_pairing_upload_cache_and_leave(self):
        transport_calls=[]
        def transport(url, method='GET', payload=None, token=None, setup_key=None):
            transport_calls.append((url,method,payload,token,setup_key))
            if url.endswith('/v1/pairs'):return {'pair_id':'idA','token':'secretA','invite_code':'invitecode123456789'}
            if url.endswith('/v1/partner'):
                return {'partner_joined':True,'partner':{'name':'Luna','game':'Ultra Moon 1.0',
                        'state':snapshot(state('Ultra Moon 1.0')),'updated_at':123456789}}
            if url.endswith('/v1/state'):return {'ok':True}
            if url.endswith('/v1/leave'):return {'ok':True}
            raise AssertionError(url)
        with tempfile.TemporaryDirectory() as directory:
            server=Service()
            sync=CompanionSync(server,directory,transport)
            output=sync.perform('create',{'worker_url':'https://unit.a.workers.dev/',
                                          'name':'Sol','game':'Ultra Sun 1.0','setup_key':'super-password-123'})
            self.assertTrue(output['configured'])
            self.assertNotIn('secretA',str(output))
            self.assertTrue((Path(directory)/'companion-credentials.json').exists())
            sync.sync_once()
            self.assertEqual(sync.status()['partner']['name'],'Luna')
            self.assertFalse(sync.status()['invite_code'])
            self.assertEqual(transport_calls[1][1],'PUT')
            first_count=len(transport_calls)
            sync.sync_once()
            self.assertEqual(len(transport_calls),first_count+1)  # no duplicate upload
            server.current['stale']=True
            sync.sync_once()
            self.assertEqual(transport_calls[-1][1],'GET')  # still reads remote but no stale upload
            fresh=CompanionSync(server,directory,transport)
            self.assertEqual(fresh.status()['partner']['name'],'Luna')
            sync.perform('leave')
            self.assertFalse(sync.settings)
            self.assertFalse((Path(directory)/'companion-cache.json').exists())

    def test_companion_http_requires_local_token(self):
        with tempfile.TemporaryDirectory() as directory:
            sync=CompanionSync(Service(),directory,lambda *a,**k:None)
            httpd=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Service(),'local-secret',sync))
            thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
            url=f'http://127.0.0.1:{httpd.server_port}/api/companion'
            try:
                with urlopen(url) as response:
                    self.assertFalse(json.load(response)['configured'])
                req=Request(url,json.dumps({'action':'leave'}).encode(),
                            {'Content-Type':'application/json'},method='POST')
                with self.assertRaises(HTTPError) as caught:urlopen(req)
                self.assertEqual(caught.exception.code,403)
                caught.exception.close()
            finally:
                httpd.shutdown();httpd.server_close();thread.join()


HOSTILE = '<img src=x onerror=alert(1)>'


def hostile_variants():
    """Field values a malicious partner/Worker could send; each must be rejected."""
    return [
        ('hp', HOSTILE), ('max_hp', '1'), ('hp', -1), ('hp', 1000), ('hp', True),
        ('level', 0), ('level', 101), ('level', '50'), ('met_level', 200),
        ('stats', {'ATQ': 'x'}), ('stats', {'ATQ': 1000}), ('stats', [1, 2]),
        ('stats', {HOSTILE: 1}), ('iv', [31] * 5), ('iv', [32] * 6), ('iv', HOSTILE),
        ('ev', ['0'] * 6), ('ev', [256] * 6), ('move_names', 'abc'),
        ('move_names', [HOSTILE, 'B', 'C', 'D']), ('move_names', ['A'] * 5),
        ('moves', [1, 2, 3, HOSTILE]), ('moves', [1] * 5), ('move_pp', [-1, 0, 0, 0]),
        ('species', HOSTILE), ('ability', 'x' * 500), ('item', 7), ('nature', HOSTILE),
        ('met_location', 'a\x00b'), ('egg_location', HOSTILE), ('met_date', HOSTILE),
        ('types', [HOSTILE]), ('types', 'Fuego'), ('type_source', HOSTILE),
        ('egg', 'yes'), ('form', -1), ('slot', HOSTILE), ('encryption_constant', 2 ** 40),
        ('origin_version', HOSTILE), ('ability_id', -3), ('item_id', 1.5),
        ('met_location_id', HOSTILE), ('egg_location_id', [1]),
        ('base_stats', {'HP': HOSTILE}), ('base_stats', [1, 2]),
        ('evolutions', HOSTILE), ('evolutions', [{'target': 1, 'method': HOSTILE}]),
        ('evolutions', [{'target': HOSTILE}]), ('evolutions', [{'target': 2}] * 65),
    ]


class HostileSnapshotTests(unittest.TestCase):
    def assert_clean(self, shared, field):
        # Property: no markup survives, and any kept field passes strict validation.
        raw = json.dumps(shared, ensure_ascii=False)
        self.assertNotIn('<', raw)
        self.assertNotIn('>', raw)
        for record in [*shared['party'], *shared['boxes']['1'],
                       *(d['pokemon'] for d in shared['progress']['deaths'].values())]:
            if record and field in record:
                FIELD_CHECKS[field](field, record[field])

    def test_every_hostile_field_is_neutralised_or_dropped_without_losing_the_session(self):
        for field, value in hostile_variants():
            for where in ('party', 'box', 'death'):
                with self.subTest(field=field, value=value, where=where):
                    current = state()
                    if where == 'party':
                        current['party'][0][field] = value
                    elif where == 'box':
                        current['boxes']['1'][0][field] = value
                    else:
                        current['progress']['deaths']['33:1234']['pokemon'][field] = value
                    if field in STRICT_FIELDS:
                        with self.assertRaises(ValueError):
                            snapshot(current)
                        continue
                    shared = snapshot(current)
                    self.assert_clean(shared, field)
                    # The rest of the Pokémon is still shared.
                    self.assertEqual(shared['party'][0]['nickname'], 'Goty')

    def test_out_of_range_stat_from_ram_does_not_block_sync(self):
        current = state()
        current['party'][0]['stats'] = {'HP': 1200, 'ATK': 50}
        current['party'][0]['max_hp'] = 1200
        shared = snapshot(current)
        self.assertNotIn('stats', shared['party'][0])
        self.assertNotIn('max_hp', shared['party'][0])
        self.assertEqual(shared['party'][0]['level'], 75)

    def test_pk3ds_method_with_angle_brackets_does_not_block_sync(self):
        current = state()
        current['party'][0]['evolutions'] = [{'target': 2, 'method': 'Nivel <36>'}]
        shared = snapshot(current)
        self.assertNotIn('evolutions', shared['party'][0])
        self.assertEqual(shared['party'][0]['species'], 'Lucario')

    def test_route_mark_pokemon_is_validated(self):
        current = state()
        record = mon()
        record['met_location'] = HOSTILE
        current['progress']['route_marks'] = {'33:1234': {'kind': 'trade', 'pokemon': record}}
        self.assertNotIn('<', json.dumps(snapshot(current), ensure_ascii=False))

    def test_nickname_from_game_memory_is_neutralised_not_rejected(self):
        current = state()
        current['party'][0]['nickname'] = 'A<b>'
        shared = snapshot(current)
        nickname = shared['party'][0]['nickname']
        self.assertNotIn('<', nickname)
        self.assertNotIn('>', nickname)
        self.assertFalse(any(ord(c) < 32 or ord(c) == 127 for c in nickname))
        current['party'][0]['nickname'] = 'x' * 500
        self.assertEqual(len(snapshot(current)['party'][0]['nickname']), 40)

    def test_legitimate_demo_snapshot_with_boxes_evolutions_and_none_stats_is_accepted(self):
        from tracker.demo import DemoService
        with tempfile.TemporaryDirectory() as directory:
            demo = DemoService(Path(directory) / 'state.json')
            current = demo.snapshot()
            current['boxes'] = {'1': demo.box_data(1), '2': demo.box_data(2)}
            party = current['party'][0]
            party['base_stats'] = {'HP': 85, 'ATK': 60, 'DEF': 65, 'SPA': 135, 'SPD': 105, 'SPE': 100}
            party['evolutions'] = [{'target': 637, 'method': 'Subir de nivel al nivel 59', 'raw_method': '4',
                                    'form': -1, 'source': 'pk3DS Progressive', 'item': 'Piedra Fuego',
                                    'target_form': 0, 'target_name': 'Volcarona', 'sprite_id': 637}]
            current['party'][1]['met_date'] = None
            shared = snapshot(current)
        self.assertIsNone(shared['boxes']['1'][0]['hp'])
        self.assertIsNone(shared['boxes']['1'][0]['stats'])
        self.assertEqual(shared['party'][0]['base_stats']['SPA'], 135)
        self.assertEqual(shared['party'][0]['evolutions'][0]['target_name'], 'Volcarona')
        self.assertEqual(len(shared['party'][0]['move_names']), 4)
        self.assertNotIn('analysis_moves', json.dumps(shared))
        # Round-trip: what we send must be accepted by the receiving side unchanged.
        self.assertEqual(viewer_state(shared)['party'], shared['party'])

    def test_viewer_state_rebuilds_and_rejects_hostile_remote_state(self):
        shared = snapshot(state('Ultra Moon 1.0'))
        shared['party'][0]['unexpected'] = HOSTILE
        self.assertNotIn('unexpected', json.dumps(viewer_state(shared)))
        for field, value in (('hp', HOSTILE), ('stats', {'ATQ': 'x'}), ('move_names', 'abc'),
                             ('species', HOSTILE)):
            with self.subTest(field=field):
                bad = snapshot(state('Ultra Moon 1.0'))
                bad['party'][0][field] = value
                viewed = viewer_state(bad)
                self.assertNotIn('<', json.dumps(viewed, ensure_ascii=False))
                if field in viewed['party'][0]:
                    FIELD_CHECKS[field](field, viewed['party'][0][field])

    def test_cloud_partner_state_is_sanitised_before_reaching_the_ui(self):
        hostile = snapshot(state('Ultra Moon 1.0'))
        hostile['party'][0]['hp'] = HOSTILE
        extra = snapshot(state('Ultra Moon 1.0'))
        extra['party'][0]['injected'] = HOSTILE
        extra['debug'] = HOSTILE
        responses = {'state': hostile, 'name': 'Luna'}

        def transport(url, method='GET', payload=None, token=None, setup_key=None):
            if url.endswith('/v1/pairs'):
                return {'pair_id': 'p', 'token': 'tok', 'invite_code': 'invitecode123456789'}
            if url.endswith('/v1/partner'):
                return {'partner_joined': True, 'partner': {'name': responses['name'], 'game': 'Ultra Moon 1.0',
                        'state': responses['state'], 'updated_at': 5}}
            return {'ok': True}

        with tempfile.TemporaryDirectory() as directory:
            sync = CompanionSync(Service(), directory, transport)
            sync.perform('create', {'name': 'Sol', 'game': 'Ultra Sun 1.0', 'setup_key': 'admin-secret-test-123'})
            sync.sync_once()
            # The hostile HP is dropped; the rest of the partner session is kept.
            self.assertNotIn(HOSTILE, json.dumps(sync.status()['partner']))
            self.assertNotIn('hp', sync.status()['partner']['state']['party'][0])
            responses['state'] = extra
            sync.sync_once()
            received = json.dumps(sync.status()['partner'])
            self.assertNotIn(HOSTILE, received)
            self.assertEqual(sync.status()['partner']['state']['party'][0]['nickname'], 'Goty')
            responses['name'] = HOSTILE
            sync.sync_once()
            self.assertNotIn(HOSTILE, json.dumps(sync.status()['partner']))
            # A tampered cache from an older version is sanitised on load.
            cache = Path(directory) / 'companion-cache.json'
            cached = json.loads(cache.read_text(encoding='utf-8'))
            cached['partner']['state']['party'][0]['hp'] = HOSTILE
            cache.write_text(json.dumps(cached), encoding='utf-8')
            reloaded = CompanionSync(Service(), directory, transport)
            self.assertNotIn(HOSTILE, json.dumps(reloaded.partner))


class PartnerNameTests(unittest.TestCase):
    def test_whitespace_partner_name_from_old_worker_is_shown_not_discarded(self):
        from companion.sync import cloud_partner
        partner = cloud_partner({'name': '   ', 'game': 'Ultra Moon 1.0', 'state': None})
        self.assertEqual(partner['name'], 'Compañero')


class FetchJsonRobustnessTests(unittest.TestCase):
    class Response:
        status = 200

        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, size=None):
            return self.body

    def test_non_object_json_is_rejected(self):
        for body in (b'[]', b'"text"', b'null', b'42'):
            with self.subTest(body=body), patch('companion.sync.urlopen', return_value=self.Response(body)):
                with self.assertRaises(ValueError):
                    fetch_json('https://a.b.workers.dev/v1/partner')

    def test_http_error_response_is_closed(self):
        import io
        body = io.BytesIO(b'{"error":"Credenciales"}')
        error = HTTPError('https://a.b.workers.dev/v1/state', 401, 'Unauthorized', {}, body)
        with patch('companion.sync.urlopen', side_effect=error):
            with self.assertRaisesRegex(ValueError, 'HTTP 401'):
                fetch_json('https://a.b.workers.dev/v1/state')
        self.assertTrue(body.closed)


class SyncThreadResilienceTests(unittest.TestCase):
    def test_unexpected_exception_is_reported_and_loop_keeps_running(self):
        calls = []
        done = threading.Event()

        def transport(url, method='GET', payload=None, token=None, setup_key=None):
            if url.endswith('/v1/pairs'):
                return {'pair_id': 'p', 'token': 'tok', 'invite_code': 'invitecode123456789'}
            calls.append(method)
            if len(calls) == 1:
                raise RuntimeError('fallo inesperado')
            if len(calls) >= 3:
                done.set()
            return {'ok': True} if method == 'PUT' else {'partner_joined': False, 'partner': None}

        with tempfile.TemporaryDirectory() as directory:
            service = Service()
            service.state = {'revision': 0}
            service.condition = threading.Condition()
            sync = CompanionSync(service, directory, transport)
            sync.retry_base = 0.01
            sync.perform('create', {'name': 'Sol', 'game': 'Ultra Sun 1.0', 'setup_key': 'admin-secret-test-123'})
            sync.start()
            try:
                self.assertTrue(done.wait(5), 'el hilo de sincronizacion murio tras la excepcion')
                self.assertTrue(sync.thread.is_alive())
            finally:
                sync.close()


class DirectLockTests(unittest.TestCase):
    def _lock_free_elsewhere(self, sync):
        result = []

        def probe_lock():
            acquired = sync.lock.acquire(timeout=0.5)
            if acquired:
                sync.lock.release()
            result.append(acquired)

        probe = threading.Thread(target=probe_lock)
        probe.start()
        probe.join()
        return bool(result and result[0])

    def test_direct_join_and_leave_do_not_hold_lock_during_network(self):
        with tempfile.TemporaryDirectory() as directory:
            sync = CompanionSync(Service(), directory)
            observed = []
            partner_state = snapshot(state('Ultra Moon 1.0'))

            def fake_request(base, path, secret, data):
                observed.append((path, self._lock_free_elsewhere(sync)))
                if path == '/v1/join':
                    return {'session': 'S' * 43, 'partner': {'name': 'Luna', 'game': 'Ultra Moon 1.0',
                            'state': partner_state, 'updated_at': 1}}
                if path == '/v1/exchange':
                    return {'partner': {'name': 'Luna', 'game': 'Ultra Moon 1.0',
                            'state': partner_state, 'updated_at': 2}}
                return {'ok': True}

            invite = 'nuzlocke://127.0.0.1:8770/join#' + 'A' * 43
            with patch('companion.sync.request_json', side_effect=fake_request):
                status = sync.perform('direct_join', {'invite_code': invite, 'name': 'Sol', 'game': 'Ultra Sun 1.0'})
                self.assertEqual(status['partner']['name'], 'Luna')
                sync.perform('leave')
                self.assertFalse(sync.status()['configured'])
                sync.perform('direct_join', {'invite_code': invite, 'name': 'Sol', 'game': 'Ultra Sun 1.0'})
                sync.close()
            paths = [path for path, _ in observed]
            self.assertIn('/v1/join', paths)
            self.assertEqual(paths.count('/v1/leave'), 2)
            for path, free in observed:
                self.assertTrue(free, path + ' se ejecuto con el candado tomado')
