import http.client,json,socket,struct,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import make_handler,frame
from tracker.service import TrackerService
class ServerTests(unittest.TestCase):
 def setUp(self):
  self.directory=tempfile.TemporaryDirectory();self.service=TrackerService(Path(self.directory.name)/'state.json')
  self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.service,'test-token'));self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):
  self.service.stop.set()
  with self.service.condition:self.service.condition.notify_all()
  self.server.shutdown();self.server.server_close();self.thread.join();self.directory.cleanup()
 def request(self,method,path,body=None,headers=None):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request(method,path,body,headers or {});r=c.getresponse();data=r.read();code=r.status;c.close();return code,data
 def test_state_and_static_assets(self):
  code,data=self.request('GET','/api/state');self.assertEqual(code,200);self.assertEqual(json.loads(data)['schema_version'],1)
  self.assertEqual(self.request('GET','/')[0],200);self.assertEqual(self.request('GET','/../server.py')[0],404)
 def test_save_diagnostic_backend_endpoint_and_permission(self):
  path='/api/diagnostic/save'
  self.service.diagnostic={'mode':'dynamic','pid':142,'regions_scanned':1100}
  self.assertEqual(self.request('POST',path,'{}')[0],403)
  headers={'X-Tracker-Token':'test-token'}
  self.assertEqual(self.request('POST',path,'{}',{**headers,'Origin':'https://external.example'})[0],403)
  code,response=self.request('POST',path,'{}',headers)
  self.assertEqual(code,200)
  saved=Path(json.loads(response)['path'])
  self.assertTrue(saved.is_file())
  self.assertEqual(saved.parent,(self.service.output.parent/'diagnosticos').resolve())
  self.assertEqual(json.loads(saved.read_text(encoding='utf-8'))['diagnostic']['pid'],142)
  self.assertEqual(self.request('GET','/api/diagnostic')[0],200)

 def test_commands_require_token_and_same_origin(self):
  body=json.dumps({'action':'scan'});self.assertEqual(self.request('POST','/api/command',body)[0],403)
  self.assertEqual(self.request('POST','/api/command',body,{'X-Tracker-Token':'test-token','Origin':'https://example.com'})[0],403)
  self.assertEqual(self.request('POST','/api/command',body,{'X-Tracker-Token':'test-token'})[0],202);self.assertEqual(self.service.commands.get_nowait(),{'action':'scan'})
 def test_invalid_box_rejected(self):
  self.assertEqual(self.request('POST','/api/command',json.dumps({'action':'box','number':33}),{'X-Tracker-Token':'test-token'})[0],400)
 def test_websocket_snapshot_and_change(self):
  s=socket.create_connection(('127.0.0.1',self.server.server_port));s.settimeout(2)
  s.sendall((f'GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n').encode());f=s.makefile('rb');self.assertIn(b'101',f.readline())
  while f.readline()!=b'\r\n':pass
  def receive():
   head=f.read(2);length=head[1]&127
   if length==126:length=struct.unpack('!H',f.read(2))[0]
   elif length==127:length=struct.unpack('!Q',f.read(8))[0]
   return json.loads(f.read(length))
  self.assertEqual(receive()['revision'],0);self.service.update(stale=False);self.assertEqual(receive()['revision'],1);f.close();s.close()
 def test_frame_large_payload(self):self.assertEqual(frame('x'*70000)[1],127)

 def test_reference_endpoints(self):
  code,data=self.request('GET','/api/move/503');self.assertEqual(code,200);self.assertEqual(json.loads(data)['power'],80)
  self.assertEqual(self.request('GET','/api/move/9999')[0],404)
  code,data=self.request('GET','/api/routes');self.assertEqual(code,200);self.assertEqual(len(json.loads(data)['routes']),90)
  self.assertEqual(self.request('GET','/empty-pokemon.svg')[0],200)

 def test_analysis_endpoint(self):
  code,data=self.request('GET','/api/analysis');self.assertEqual(code,200);value=json.loads(data)
  self.assertEqual(value['chart']['Eléctrico']['Tierra'],0);self.assertEqual(len(value['types']),18)

 def test_route_miss_command(self):
  headers={'X-Tracker-Token':'test-token'}
  valid={'action':'route_miss','route':'8','missed':True}
  self.assertEqual(self.request('POST','/api/command',json.dumps(valid),headers)[0],202)
  self.service.handle(self.service.commands.get_nowait())
  code,data=self.request('GET','/api/state');self.assertEqual(json.loads(data)['progress']['missed_routes'],['8'])
  for value in (dict(valid,route='no-route'),dict(valid,missed='yes')):
   self.assertEqual(self.request('POST','/api/command',json.dumps(value),headers)[0],400)

 def test_revive_and_bundled_font(self):
  pokemon={'encryption_constant':12,'origin_version':33,'checksum_valid':True,'hp':0,'max_hp':10}
  self.service.update(party=[pokemon],stale=False)
  headers={'X-Tracker-Token':'test-token'}
  body=json.dumps({'action':'revive','key':'33:12'})
  self.assertEqual(self.request('POST','/api/command',body,headers)[0],202)
  self.service.handle(self.service.commands.get_nowait())
  self.assertFalse(self.service.snapshot()['progress']['deaths'])
  self.assertEqual(self.request('POST','/api/command',json.dumps({'action':'revive','key':'unknown'}),headers)[0],400)
  code,font=self.request('GET','/fonts/Oxanium.ttf');self.assertEqual(code,200);self.assertTrue(font.startswith(b'\x00\x01\x00\x00'))
