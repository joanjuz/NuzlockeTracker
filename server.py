"""Loopback HTTP + WebSocket server, using the Python standard library."""
import argparse,base64,hashlib,json,re,secrets,socket,struct,sys,threading,webbrowser
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
from tracker.service import TrackerService
from companion.sync import CompanionSync
ROOT=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))

def runtime_directory(root, profile=None):
    """Separate game state, progress, partner credentials and cache for each local player."""
    base=Path(root)/'runtime'
    if profile is None:
        return base  # Keep existing accounts/credentials in the original location.
    if not isinstance(profile,str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,31}',profile):
        raise ValueError('Perfil invalido: usa entre 1 y 32 letras minusculas, numeros, _ o -')
    return base/'profiles'/profile

def frame(payload,opcode=1):
    raw=payload.encode() if isinstance(payload,str) else payload
    size=len(raw);return bytes([128|opcode])+(bytes([size]) if size<126 else b'\x7e'+struct.pack('!H',size) if size<65536 else b'\x7f'+struct.pack('!Q',size))+raw

def make_handler(service,token,companion=None,profile='principal'):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def allowed(self):
            host=f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host')==host and self.headers.get('Origin',f'http://{host}')==f'http://{host}'
        def reply(self,code,data,kind='application/json'):
            raw=json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if not self.allowed():self.reply(403,{'error':'Origen inválido'});return
            path=urlsplit(self.path).path
            if path=='/api/session':self.reply(200,{'token':token,'profile':profile,'saved_connection':service.config if service.snapshot().get('session_saved') else None});return
            if path=='/api/state':self.reply(200,service.snapshot());return
            if path=='/api/templates':self.reply(200,service.templates.status());return
            if path=='/api/companion':
                if companion is None:self.reply(404,{'error':'Sin sincronización'});return
                self.reply(200,companion.status());return
            if path=='/api/analysis':
                self.reply(200,{k:v for k,v in service.reference.analysis.items() if k!='pokemon'});return
            if path=='/api/routes':self.reply(200,service.reference.routes(service.snapshot()['game']));return
            if path.startswith('/api/move/'):
                try:
                    suffix=path[len('/api/move/'): ]
                    if not suffix.isdigit():raise ValueError('ID inválido')
                    self.reply(200,service.reference.move(int(suffix),service.catalog))
                except ValueError as exc:self.reply(404,{'error':str(exc)})
                return
            if path=='/api/diagnostic':self.reply(200,{'connection':service.snapshot()['connection'],'game':service.snapshot()['game'],'details':service.diagnostic or {}});return
            if path=='/ws':
                if self.headers.get('Upgrade','').lower()!='websocket' or self.headers.get('Sec-WebSocket-Version')!='13':self.reply(400,{});return
                key=self.headers.get('Sec-WebSocket-Key','')
                try:
                    if len(base64.b64decode(key,validate=True))!=16:raise ValueError()
                except ValueError:self.reply(400,{});return
                accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
                self.send_response(101);self.send_header('Upgrade','websocket');self.send_header('Connection','Upgrade');self.send_header('Sec-WebSocket-Accept',accept);self.end_headers()
                self.connection.settimeout(3);revision=-1
                try:
                    while not service.stop.is_set():
                        state=service.snapshot()
                        if state['revision']!=revision:
                            self.connection.sendall(frame(json.dumps(state,ensure_ascii=False)));revision=state['revision']
                        with service.condition:service.condition.wait_for(lambda:service.state['revision']!=revision or service.stop.is_set(),timeout=10)
                        if service.snapshot()['revision']==revision:self.connection.sendall(frame(b'',9))
                except OSError:pass
                self.close_connection=True;return
            files={'/fonts/Oxanium.ttf':('web/fonts/Oxanium.ttf','font/ttf'),'/':('web/index.html','text/html; charset=utf-8'),'/app.js':('web/app.js','text/javascript; charset=utf-8'),'/analysis.js':('web/analysis.js','text/javascript; charset=utf-8'),'/companion.js':('web/companion.js','text/javascript; charset=utf-8'),'/companion.css':('web/companion.css','text/css; charset=utf-8'),'/style.css':('web/style.css','text/css; charset=utf-8'),'/empty-pokemon.svg':('web/empty-pokemon.svg','image/svg+xml')}
            if path in files:
                name,kind=files[path];self.reply(200,(ROOT/name).read_bytes(),kind);return
            if path.startswith('/sprites/') and path[9:].removesuffix('.png').isdigit() and path.endswith('.png'):
                file=ROOT/'data'/'sprites'/path[9:]
                if file.is_file():self.reply(200,file.read_bytes(),'image/png');return
            self.reply(404,{})
        def do_POST(self):
            if not self.allowed() or self.headers.get('X-Tracker-Token')!=token:self.reply(403,{});return
            if self.path=='/api/companion':
                if companion is None:self.reply(404,{'error':'Sin sincronización'});return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=4096:raise ValueError('Solicitud demasiado grande')
                    cmd=json.loads(self.rfile.read(size))
                    if not isinstance(cmd,dict):raise ValueError('JSON incorrecto')
                    action=cmd.get('action')
                    if action not in ('create','join','refresh','leave'):raise ValueError('Acción inválida')
                    self.reply(200,companion.perform(action,cmd))
                except (ValueError,TypeError) as exc:self.reply(400,{'error':str(exc)})
                return
            if self.path=='/api/diagnostic/save':
                try:
                    self.reply(200,{'ok':True,'path':service.save_diagnostic()})
                except OSError as exc:
                    self.reply(500,{'error':'No se pudo guardar el archivo: '+str(exc)})
                return
            if self.path=='/api/templates':
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=500000:raise ValueError('Plantilla demasiado grande')
                    data=json.loads(self.rfile.read(length))
                    if not isinstance(data,dict):raise ValueError('Plantillas inválidas')
                    self.reply(200,service.import_templates(data.get('files')))
                except (ValueError,TypeError,UnicodeError,KeyError) as error:
                    self.reply(400,{'error':str(error)})
                return
            if self.path!='/api/command':self.reply(404,{});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096:raise ValueError('Tamaño inválido')
                cmd=json.loads(self.rfile.read(size));action=cmd.get('action')
                if action not in ('connect','disconnect','box','scan','cancel','demo','route_miss','revive','mark_dead','save_session'):raise ValueError('Acción inválida')
                if action=='revive':service.validate_revive(cmd)
                if action=='mark_dead':service.validate_mark_dead(cmd)
                if action=='route_miss':service.validate_route_miss(cmd)
                if action=='demo' and (not service.snapshot().get('demo') or cmd.get('scenario') not in ('normal','damage','empty','stale','long')):raise ValueError('Escenario de demostración inválido')
                if action=='connect':
                    from tracker.profiles import PROFILES
                    if cmd.get('game','Ultra Moon 1.0') not in PROFILES:raise ValueError('Juego no compatible')
                    if cmd.get('mode') not in ('memory','gdb'):raise ValueError('Conector inválido')
                    if cmd.get('pid') is not None and (type(cmd['pid']) is not int or cmd['pid']<=0):raise ValueError('PID inválido')
                    if type(cmd.get('port',24689)) is not int or not 1<=cmd.get('port',24689)<=65535:raise ValueError('Puerto inválido')
                if action=='box' and (type(cmd.get('number')) is not int or not 1<=cmd['number']<=32):raise ValueError('Caja inválida')
                if action in ('connect','disconnect'):cmd['_connection_generation']=service.request_connection_change()
                service.commands.put(cmd);self.reply(202,{'ok':True})
            except (ValueError,AttributeError,TypeError) as exc:self.reply(400,{'error':str(exc)})
    return Handler

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');parser.add_argument('--demo',action='store_true',help='Interfaz con datos simulados, sin emulador');parser.add_argument('--profile',help='Perfil local independiente (ej. segundo-jugador)');args=parser.parse_args()
    try:runtime=runtime_directory(ROOT,args.profile)
    except ValueError as error:parser.error(str(error))
    if args.demo:
        from tracker.demo import DemoService
        service=DemoService(runtime/'demo-state.json')
    else:service=TrackerService(runtime/'state.json')
    companion=CompanionSync(service,runtime)
    companion.start()
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(service,secrets.token_urlsafe(32),companion,profile=args.profile or 'principal'))
    worker=threading.Thread(target=service.run,daemon=True);worker.start()
    url=f'http://127.0.0.1:{server.server_port}/';print('Tracker local: '+url+'\nPerfil: '+(args.profile or 'principal')+'\nMantén esta ventana abierta. Ctrl+C para cerrar.')
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:service.stop.set();companion.close();server.server_close()
if __name__=='__main__':main()
