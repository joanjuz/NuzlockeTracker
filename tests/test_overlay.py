"""OBS browser source: portable configuration, live PS and read-only privacy."""
import base64
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer

from tracker.overlay import OverlayManager, DEFAULT, validated_settings
from tracker.layout_export import blank_sprite
from tracker.service import TrackerService
from server import make_handler, RemoteOverlayShare


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.service = TrackerService(self.root/'runtime'/'state.json')
        self.layout = self.root/'layout'
        self.layout.mkdir()
        self.manager = OverlayManager(self.service, self.root/'runtime', self.layout)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),
            make_handler(self.service,'test-token',overlay=self.manager))
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def req(self, method, path, payload=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        body = json.dumps(payload) if payload is not None else None
        conn.request(method,path,body,headers or {})
        response=conn.getresponse()
        status=response.status
        data=response.read()
        headers=dict(response.getheaders())
        conn.close()
        return status,data,headers

    def test_live_party_is_sanitized_and_stays_read_only(self):
        mon={'species_id':25,'nickname':'Chispa','species':'Pikachu','hp':30,'max_hp':100,
             'encryption_constant':125,'origin_version':33,'secret_token':'never-export'}
        self.service.update(party=[mon]+[None]*5,boxes={'1':[mon]+[None]*29},stale=False)
        status,raw,_=self.req('GET','/api/overlay/public')
        self.assertEqual(status,200)
        result=json.loads(raw)
        self.assertEqual(len(result['party']),6)
        self.assertEqual(result['party'][0]['nickname'],'Chispa')
        self.assertEqual(result['party'][0]['percent'],30)
        self.assertEqual(result['party'][1],{'slot':2,'present':False})
        self.assertNotIn('secret_token',raw.decode())
        self.assertNotIn('encryption_constant',raw.decode())
        self.assertNotIn('boxes',raw.decode())
        self.assertNotIn('token',raw.decode())
        self.assertNotIn('pid',raw.decode())
        self.assertNotIn('progress',raw.decode())
        self.service.update(party=[{**mon,'hp':5}]+[None]*5,stale=False)
        data=json.loads(self.req('GET','/api/overlay/public')[1])
        self.assertEqual(data['party'][0]['percent'],5)
        self.service.progress.mark_dead({**mon, 'checksum_valid':True})
        self.service.update(stale=True)
        data=json.loads(self.req('GET','/api/overlay/public')[1])
        self.assertTrue(data['party'][0]['dead'])
        self.assertTrue(data['party'][0]['stale'])

    def test_settings_persist_and_input_is_strict(self):
        setting={**DEFAULT,'hp_good':'#abc123','font':'Verdana','order':['names','hp','sprites'],
                 'hp_reverse':True,'gap':27,'hp_label':'percent','hp_style':'striped'}
        self.assertEqual(self.req('POST','/api/overlay/settings',setting)[0],403)
        self.assertEqual(self.req('POST','/api/overlay/settings',setting,
             {'X-Tracker-Token':'test-token','Origin':'https://other.example'})[0],403)
        status,raw,_=self.req('POST','/api/overlay/settings',setting,{'X-Tracker-Token':'test-token'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['hp_good'],'#abc123')
        again=OverlayManager(self.service,self.root/'runtime',self.layout)
        self.assertEqual(again.get_settings()['order'],setting['order'])
        self.assertEqual(self.req('GET','/api/overlay/settings')[0],200)
        for changes in ({'hp_good':'red'}, {'order':['sprites','sprites','hp']},
                        {'gap':-1},{'hp_glow':'true'},{'unknown':True},
                        {'font_file':'../../credentials.json'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.req('POST','/api/overlay/settings',changes,
                    {'X-Tracker-Token':'test-token'})[0],400)
        self.assertEqual(self.manager.get_settings()['hp_good'],'#abc123')

    def test_custom_font_import_rejects_traversal_and_is_local(self):
        fake_font=base64.b64encode(b'\x00\x01\x00\x00'+b'\0'*100).decode()
        invalid={'name':'../../secret.ttf','data':fake_font}
        valid={'name':'Mi_Fuente.ttf','data':fake_font}
        self.assertEqual(self.req('POST','/api/overlay/font',valid)[0],403)
        headers={'X-Tracker-Token':'test-token'}
        self.assertEqual(self.req('POST','/api/overlay/font',invalid,headers)[0],400)
        status,raw,_=self.req('POST','/api/overlay/font',valid,headers)
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw),['Mi_Fuente.ttf'])
        status,font,response=self.req('GET','/overlay/font/Mi_Fuente.ttf')
        self.assertEqual(status,200)
        self.assertEqual(font[:4],b'\x00\x01\x00\x00')
        self.assertIn('font/ttf',response['Content-Type'])
        self.assertEqual(self.req('GET','/overlay/font/..%2fsecret.ttf')[0],404)
        saved=self.req('POST','/api/overlay/settings',
                       {**DEFAULT,'font_file':'Mi_Fuente.ttf'},headers)
        self.assertEqual(saved[0],200)

    def test_import_custom_hp_png_and_validate_assets(self):
        self.assertEqual(self.req('GET','/overlay/hp-image/fill.png')[0],404)
        self.assertEqual(self.req('GET','/overlay/hp-image/../../state.json')[0],404)
        raw=blank_sprite(96)
        value={'kind':'fill','data':base64.b64encode(raw).decode()}
        self.assertEqual(self.req('POST','/api/overlay/hp-image',value)[0],403)
        status,body,_=self.req('POST','/api/overlay/hp-image',value,
                               {'X-Tracker-Token':'test-token'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['kind'],'fill')
        got=self.req('GET','/overlay/hp-image/fill.png')
        self.assertEqual(got[0],200)
        self.assertEqual(got[1][:8],b'\x89PNG\r\n\x1a\n')
        self.assertNotEqual(self.manager.hp_asset_versions()['fill'],'0')
        self.assertEqual(self.req('POST','/api/overlay/hp-image',
            {'kind':'../../runtime', 'data':value['data']},
            {'X-Tracker-Token':'test-token'})[0],400)
        self.assertEqual(self.req('POST','/api/overlay/hp-image',
            {'kind':'frame','data':base64.b64encode(b'NOTPNG').decode()},
            {'X-Tracker-Token':'test-token'})[0],400)
        config={**DEFAULT,'hp_custom_fill':True}
        self.assertEqual(self.req('POST','/api/overlay/settings',config,
            {'X-Tracker-Token':'test-token'})[0],200)
        saved=OverlayManager(self.service,self.root/'runtime',self.layout)
        self.assertTrue(saved.get_settings()['hp_custom_fill'])
        get=self.req('GET','/api/overlay/settings')
        self.assertIn('hp_asset_versions',json.loads(get[1]))

    def test_custom_sprite_import_from_editor_is_local_safe_and_native(self):
        from PIL import Image
        from io import BytesIO
        buffer=BytesIO()
        Image.new('RGBA',(128,128),(10,90,240,109)).save(buffer,format='PNG')
        payload=base64.b64encode(buffer.getvalue()).decode()
        valid={'name':'025.png','data':payload}
        self.assertEqual(self.req('POST','/api/overlay/sprite',valid)[0],403)
        headers={'X-Tracker-Token':'test-token'}
        status,raw,_=self.req('POST','/api/overlay/sprite',valid,headers)
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['name'],'025.png')
        output=self.layout.parent/'sprites_personalizados'/'025.png'
        self.assertEqual(output.read_bytes(),buffer.getvalue())
        for invalid in ('../../025.png','C:\\\\file.png','25.svg','wrong','é.png'):
            with self.subTest(invalid=invalid):
                response=self.req('POST','/api/overlay/sprite',
                    {'name':invalid,'data':payload},headers)
                self.assertEqual(response[0],400)
        self.assertEqual(self.req('POST','/api/overlay/sprite',
            {'name':'025.png','data':base64.b64encode(b'broken').decode()},headers)[0],400)
        self.assertEqual(output.read_bytes(),buffer.getvalue())
        self.assertEqual(self.req('POST','/api/overlay/sprite',
            {'name':'25.webp','data':payload},
            {'X-Tracker-Token':'wrong-token'})[0],403)

    def test_remote_server_is_only_readable_overlay(self):
        read_only=ThreadingHTTPServer(('127.0.0.1',0),
            make_handler(self.service,'remote-token',overlay=self.manager,remote_only=True))
        thread=threading.Thread(target=read_only.serve_forever,daemon=True)
        thread.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',read_only.server_port)
            for path in ('/overlay','/overlay.js','/overlay.css','/api/overlay/public',
                         '/api/overlay/settings','/fonts/Oxanium.ttf'):
                conn.request('GET',path)
                response=conn.getresponse()
                self.assertEqual(response.status,200,path)
                response.read()
            for path in ('/api/session','/api/state','/api/command','/ws',
                         '/overlay/editor','/api/overlay/share'):
                conn.request('GET',path)
                response=conn.getresponse()
                self.assertEqual(response.status,404,path)
                response.read()
            conn.request('POST','/api/overlay/settings','{}',
                         {'X-Tracker-Token':'remote-token'})
            response=conn.getresponse()
            self.assertEqual(response.status,403)
            response.read()
            conn.close()
        finally:
            read_only.shutdown()
            read_only.server_close()
            thread.join()
        share=RemoteOverlayShare(self.service,self.manager)
        for ip in ('127.0.0.1','0.0.0.0','no-es-ip'):
            with self.subTest(ip=ip),self.assertRaises(ValueError):
                share.configure(True,ip)
        self.assertFalse(share.status()['enabled'])

    def test_browser_sources_are_transparent_and_expose_slot_images(self):
        for path in ['/overlay','/overlay/editor','/overlay.js','/overlay.css',
                     '/overlay-editor.css','/overlay-editor.js','/api/overlay/defaults']:
            with self.subTest(path=path):
                self.assertEqual(self.req('GET',path)[0],200)
        raw=blank_sprite(96)
        (self.layout/'pokemon_1.png').write_bytes(raw)
        s,body,header=self.req('GET','/overlay/media/pokemon_1.png')
        self.assertEqual(s,200)
        self.assertEqual(body,raw)
        self.assertEqual(header['Cache-Control'],'no-store')
        self.assertEqual(self.req('GET','/overlay/media/pokemon_9.png')[0],404)
        self.assertEqual(self.req('GET','/overlay/media/../state.json')[0],404)
        self.assertEqual(self.req('GET','/overlay/font/../../state.json')[0],404)
        self.assertEqual(self.req('GET','/api/overlay/private')[0],404)


if __name__ == '__main__':
    unittest.main()
