"""Loopback HTTP + WebSocket server, using the Python standard library."""
import argparse,base64,hashlib,ipaddress,json,re,secrets,socket,struct,sys,threading,time,webbrowser
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
from tracker.service import TrackerService
from companion.sync import CompanionSync
from tracker.overlay import OverlayManager, DEFAULT
from tracker.layout_export import fetch_sprite, validate_png
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

class RemoteOverlayShare:
    """Servidor independiente vinculado SOLO a la IP VPN seleccionada.

    Las rutas remotas permiten leer el overlay, nunca acceder a /api/session,
    /api/state, /api/command, /ws ni publicar cambios.
    """
    def __init__(self, service, overlay, preferred_port=8767):
        self.service = service
        self.overlay = overlay
        self.preferred_port = preferred_port
        self.lock = threading.RLock()
        self.server = None
        self.thread = None

    def status(self):
        with self.lock:
            if self.server is None:
                return {'enabled': False, 'ip': '', 'port': None, 'base_url': ''}
            ip, port = self.server.server_address[:2]
            return {'enabled': True, 'ip': ip, 'port': port,
                    'base_url': f'http://{ip}:{port}'}

    def configure(self, enabled, ip=''):
        if type(enabled) is not bool:
            raise ValueError('Estado de VPN inválido')
        if not enabled:
            self.close()
            return self.status()
        if not isinstance(ip, str):
            raise ValueError('Introduce una dirección IPv4 de tu computadora')
        try:
            address = ipaddress.IPv4Address(ip.strip())
        except ipaddress.AddressValueError as exc:
            raise ValueError('La IP VPN debe ser IPv4; por ejemplo 26.10.20.30') from exc
        if address.is_unspecified or address.is_loopback or address.is_multicast or int(address) == 0xffffffff:
            raise ValueError('Selecciona la IP de tu adaptador VPN; no 127.0.0.1 ni 0.0.0.0')
        ip = str(address)
        with self.lock:
            if self.server and self.server.server_address[0] == ip:
                return self.status()
            handler = make_handler(self.service, secrets.token_urlsafe(32),
                                   overlay=self.overlay, remote_only=True)
            try:
                server = ThreadingHTTPServer((ip, self.preferred_port), handler)
            except OSError as exc:
                # Solo intentar puerto dinámico cuando el predeterminado está ocupado.
                if getattr(exc, 'errno', None) not in (98, 10048):
                    raise ValueError('No se pudo usar esa IP. Comprueba la IP de Radmin VPN: ' + str(exc)) from exc
                server = ThreadingHTTPServer((ip, 0), handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            previous = self.server
            self.server, self.thread = server, thread
        if previous:
            previous.shutdown()
            previous.server_close()
        return self.status()

    def close(self):
        with self.lock:
            previous = self.server
            self.server = None
            self.thread = None
        if previous:
            previous.shutdown()
            previous.server_close()


def make_handler(service,token,companion=None,profile='principal',overlay=None,
                 share=None,remote_only=False,sprite_cache=None):
    # Los avisos Soul Link pueden referirse a un Pokémon guardado en cajas.
    # Resolver sprites en el servidor evita depender del acceso GitHub/WebView2
    # de cada cliente y guarda lo descargado para uso sin conexión posterior.
    sprite_dir=Path(sprite_cache) if sprite_cache is not None else None
    sprite_retry={}
    sprite_lock=threading.Lock()
    def sprite_bytes(ident):
        candidates=[ROOT/'data'/'sprites'/f'{ident}.png']
        if sprite_dir is not None:candidates.insert(0,sprite_dir/f'{ident}.png')
        for path in candidates:
            try:
                if path.is_file():return validate_png(path.read_bytes())
            except (OSError,ValueError):
                continue
        with sprite_lock:
            if time.monotonic()<sprite_retry.get(ident,0):return None
        try:
            raw=fetch_sprite(ident)
        except (OSError,ValueError):
            with sprite_lock:sprite_retry[ident]=time.monotonic()+45
            return None
        if sprite_dir is not None:
            try:
                sprite_dir.mkdir(parents=True,exist_ok=True)
                path=sprite_dir/f'{ident}.png'
                tmp=sprite_dir/f'.{ident}.{threading.get_ident()}.tmp'
                try:
                    tmp.write_bytes(raw)
                    tmp.replace(path)
                finally:tmp.unlink(missing_ok=True)
            except OSError:
                pass  # Mostrarlo aunque el cache no sea escribible.
        return raw

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def allowed(self):
            host=f'{self.server.server_address[0]}:{self.server.server_port}'
            return self.headers.get('Host')==host and self.headers.get('Origin',f'http://{host}')==f'http://{host}'
        def reply(self,code,data,kind='application/json'):
            raw=json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if not self.allowed():self.reply(403,{'error':'Origen inválido'});return
            path=urlsplit(self.path).path
            if remote_only:
                remote_files = ('/overlay', '/overlay.js', '/overlay.css',
                                '/api/overlay/public', '/api/overlay/settings',
                                '/fonts/Oxanium.ttf')
                media = (path.startswith('/overlay/media/pokemon_') or
                         path.startswith('/overlay/font/') or
                         path.startswith('/overlay/hp-image/'))
                if path not in remote_files and not media:
                    self.reply(404, {'error':'Solo lectura OBS'});return
            if path.startswith('/api/overlay/') or path.startswith('/overlay'):
                if overlay is None:self.reply(404,{});return
                if path=='/api/overlay/share':
                    if share is None or remote_only:self.reply(404,{});return
                    self.reply(200,share.status());return
                if path=='/api/overlay/public':
                    self.reply(200,overlay.public_state());return
                if path=='/api/overlay/settings':
                    config=overlay.get_settings()
                    config['hp_asset_versions']=overlay.hp_asset_versions()
                    self.reply(200,config);return
                if path=='/api/overlay/defaults':
                    self.reply(200,DEFAULT);return
                if path=='/api/overlay/fonts':
                    self.reply(200,overlay.available_fonts());return
                if path.startswith('/overlay/font/'):
                    name=path[len('/overlay/font/'):]
                    raw=overlay.font_bytes(name)
                    if raw is None:self.reply(404,{});return
                    extension=name.rsplit('.',1)[-1]
                    kind={'ttf':'font/ttf','otf':'font/otf',
                          'woff':'font/woff','woff2':'font/woff2'}.get(extension,'application/octet-stream')
                    self.reply(200,raw,kind);return
                if path.startswith('/overlay/hp-image/'):
                    match=re.fullmatch(r'/overlay/hp-image/(fill|frame)\.png',path)
                    if not match:self.reply(404,{});return
                    raw=overlay.hp_image_bytes(match[1])
                    if raw is None:self.reply(404,{});return
                    self.reply(200,raw,'image/png');return
                if path.startswith('/overlay/media/pokemon_'):
                    match=re.fullmatch(r'/overlay/media/pokemon_([1-6])\.(gif|png)',path)
                    if not match:self.reply(404,{});return
                    raw=overlay.image_bytes(int(match[1]),match[2])
                    self.reply(200,raw,'image/'+match[2]);return
                overlay_files={
                    '/overlay':('web/overlay.html','text/html; charset=utf-8'),
                    '/overlay/editor':('web/overlay-editor.html','text/html; charset=utf-8'),
                    '/overlay.js':('web/overlay.js','text/javascript; charset=utf-8'),
                    '/overlay.css':('web/overlay.css','text/css; charset=utf-8'),
                    '/overlay-editor.js':('web/overlay-editor.js','text/javascript; charset=utf-8'),
                    '/overlay-editor.css':('web/overlay-editor.css','text/css; charset=utf-8'),
                }
                if path in overlay_files:
                    name,kind=overlay_files[path]
                    self.reply(200,(ROOT/name).read_bytes(),kind)
                    return
                self.reply(404,{});return
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
            files={'/fonts/Oxanium.ttf':('web/fonts/Oxanium.ttf','font/ttf'),'/':('web/index.html','text/html; charset=utf-8'),'/app.js':('web/app.js','text/javascript; charset=utf-8'),'/analysis.js':('web/analysis.js','text/javascript; charset=utf-8'),'/companion.js':('web/companion.js','text/javascript; charset=utf-8'),'/companion.css':('web/companion.css','text/css; charset=utf-8'),'/style.css':('web/style.css','text/css; charset=utf-8'),'/empty-pokemon.svg':('web/empty-pokemon.svg','image/svg+xml'),'/app-icon.png':('web/app-icon.png','image/png')}
            if path in files:
                name,kind=files[path];self.reply(200,(ROOT/name).read_bytes(),kind);return
            match=re.fullmatch(r'/soullink/sprite/([1-9][0-9]{0,4})\.png',path)
            if match and 1<=int(match[1])<=10115:
                raw=sprite_bytes(int(match[1]))
                if raw is not None:
                    self.reply(200,raw,'image/png')
                    return
            # La galería general conserva su ruta habitual: no disparar
            # cientos de descargas al abrir todas las cajas del tracker.
            if path.startswith('/sprites/') and path[9:].removesuffix('.png').isdigit() and path.endswith('.png'):
                file=ROOT/'data'/'sprites'/path[9:]
                if file.is_file():self.reply(200,file.read_bytes(),'image/png');return
            self.reply(404,{})
        def do_POST(self):
            if remote_only:self.reply(403,{'error':'Solo lectura OBS'});return
            if not self.allowed() or self.headers.get('X-Tracker-Token')!=token:self.reply(403,{});return
            if self.path=='/api/overlay/share':
                if share is None:self.reply(404,{});return
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=256:raise ValueError('Solicitud demasiado grande')
                    data=json.loads(self.rfile.read(length))
                    if not isinstance(data,dict):raise ValueError('Solicitud incorrecta')
                    self.reply(200,share.configure(data.get('enabled'),data.get('ip','')))
                except (ValueError,TypeError,OSError) as exc:
                    self.reply(400,{'error':str(exc)})
                return
            if self.path in ('/api/overlay/settings','/api/overlay/font','/api/overlay/hp-image'):
                if overlay is None:self.reply(404,{});return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    limit=4300000 if self.path.endswith('/font') else 3000000 if self.path.endswith('/hp-image') else 8192
                    if not 0<size<=limit:raise ValueError('Solicitud de overlay demasiado grande')
                    obj=json.loads(self.rfile.read(size))
                    if not isinstance(obj,dict):raise ValueError('JSON inválido')
                    if self.path.endswith('/font'):
                        result=overlay.import_font(obj.get('name'),obj.get('data'))
                    elif self.path.endswith('/hp-image'):
                        result=overlay.import_hp_image(obj.get('kind'),obj.get('data'))
                    else:
                        result=overlay.set_settings(obj)
                    self.reply(200,result)
                except (ValueError,TypeError,UnicodeError) as exc:
                    self.reply(400,{'error':str(exc)})
                return
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
                if action not in ('connect','disconnect','box','scan','cancel','demo','route_miss','revive','mark_dead','set_origin','mark_route','clear_route_mark','save_session'):raise ValueError('Acción inválida')
                if action=='revive':service.validate_revive(cmd)
                if action=='mark_dead':service.validate_mark_dead(cmd)
                if action=='route_miss':service.validate_route_miss(cmd)
                if action=='set_origin':service.validate_set_origin(cmd)
                if action=='mark_route':service.validate_route_mark(cmd)
                if action=='clear_route_mark':service.validate_route_mark(cmd,undo=True)
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
    overlay=OverlayManager(service,runtime,runtime/'layout')
    share=RemoteOverlayShare(service,overlay)
    server=ThreadingHTTPServer(('127.0.0.1',0),
        make_handler(service,secrets.token_urlsafe(32),companion,
                     profile=args.profile or 'principal',overlay=overlay,share=share,
                     sprite_cache=runtime.parent/'sprite-cache'))
    worker=threading.Thread(target=service.run,daemon=True);worker.start()
    url=f'http://127.0.0.1:{server.server_port}/';print('Tracker local: '+url+'\nPerfil: '+(args.profile or 'principal')+'\nMantén esta ventana abierta. Ctrl+C para cerrar.')
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:service.stop.set();share.close();companion.close();server.server_close()
if __name__=='__main__':main()
