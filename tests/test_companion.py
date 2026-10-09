import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from companion.snapshot import snapshot, viewer_state
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
            finally:
                httpd.shutdown();httpd.server_close();thread.join()
