"""Loopback HTTP + WebSocket server, using the Python standard library.

Las rutas HTTP viven en tracker/api/ (tabla de rutas por módulo); este
archivo conserva el servidor, la publicación por VPN y el lanzador.
"""
import argparse,ipaddress,secrets,socket,sys,threading,webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from companion.sync import CompanionSync
from tracker.overlay import OverlayManager
from tracker.run_profiles import valid_profile_id
from tracker import __version__, diaglog
# Re-exportados: desktop.py y las pruebas importan estos nombres desde server.
from tracker.api import make_handler, frame, content_security_policy  # noqa: F401
ROOT=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))

class TrackerHTTPServer(ThreadingHTTPServer):
    # Windows otherwise permits a second HTTPServer to bind the same address,
    # which can mix independent runs' responses instead of falling back safely.
    allow_reuse_address = False
    request_queue_size = 128
    daemon_threads = True
    def server_bind(self):
        if sys.platform=='win32':
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

def runtime_directory(root, profile=None):
    """Separate game state, progress, partner credentials and cache for each local player."""
    base=Path(root)/'runtime'
    if profile is None or profile == 'principal':
        return base  # Keep existing accounts/credentials in the original location.
    if not valid_profile_id(profile):
        raise ValueError('Perfil invalido: usa entre 1 y 32 letras minusculas, numeros, _ o -')
    return base/'profiles'/profile

def companion_directory(runtime,demo=False):
    """Demo data must never reach a real Soul Link pair: give it an empty,
    separate credential folder instead of the profile's companion files."""
    return Path(runtime)/'demo-companion' if demo else Path(runtime)

class RemoteOverlayShare:
    """Servidor independiente vinculado SOLO a la IP VPN seleccionada.

    Las rutas remotas permiten leer el overlay, nunca acceder a /api/session,
    /api/state, /api/command, /ws ni publicar cambios.
    """
    def __init__(self, service, overlay, preferred_port=8767, sprite_cache=None):
        self.service = service
        self.overlay = overlay
        self.sprite_cache = sprite_cache  # Item icons for OBS over the VPN.
        self.layout = None  # PartyLayoutExporter, set once it exists (graveyard sprites).
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
                                   overlay=self.overlay, remote_only=True,
                                   sprite_cache=self.sprite_cache, layout=self.layout)
            try:
                server = TrackerHTTPServer((ip, self.preferred_port), handler)
            except OSError as exc:
                # Solo intentar puerto dinámico cuando el predeterminado está ocupado.
                if getattr(exc, 'errno', None) not in (98, 10048):
                    raise ValueError('No se pudo usar esa IP. Comprueba la IP de Radmin VPN: ' + str(exc)) from exc
                server = TrackerHTTPServer((ip, 0), handler)
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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');parser.add_argument('--demo',action='store_true',help='Interfaz con datos simulados, sin emulador');parser.add_argument('--profile',help='Perfil local independiente (ej. segundo-jugador)');args=parser.parse_args()
    try:runtime=runtime_directory(ROOT,args.profile)
    except ValueError as error:parser.error(str(error))
    diaglog.setup(runtime/'logs','demo' if args.demo else (args.profile or 'principal'))
    diaglog.get('app').info('Inicio server.py %s%s',__version__,' (demo)' if args.demo else '')
    if not args.demo:
        # Reuse the desktop lifecycle so named runs behave the same in the
        # browser launcher, including locking and safe profile switches.
        from desktop import LocalBackend
        backend=LocalBackend(runtime,args.profile or 'principal',
            layout_path=runtime/'layout',sprite_cache=ROOT/'sprite-cache',
            custom_dir=ROOT/'sprites_personalizados',check_updates=True)
        try:
            backend.start()
            print('Tracker local: '+backend.url+'\nMantén esta ventana abierta. Ctrl+C para cerrar.')
            if not args.no_browser:webbrowser.open(backend.url)
            while backend.http_thread.is_alive():backend.http_thread.join(timeout=.5)
        except KeyboardInterrupt:pass
        finally:backend.close();diaglog.close()
        return
    # Only the demo reaches this point (the normal launcher returned above).
    from tracker.demo import DemoService
    from tracker.layout_export import PartyLayoutExporter
    service=DemoService(runtime/'demo-state.json')
    companion=CompanionSync(service,companion_directory(runtime,True))
    companion.start()
    # Own folder: demo sprites never overwrite a real run's OBS layout files.
    demo_layout=runtime/'demo-layout'
    overlay=OverlayManager(service,runtime/'demo-overlay',demo_layout,custom_dir=demo_layout/'sprites_personalizados')
    layout=PartyLayoutExporter(service,demo_layout,cache_dir=ROOT/'sprite-cache',
                               custom_dir=demo_layout/'sprites_personalizados',
                               sprite_set=overlay.selected_sprite_set)
    layout.start()
    share=RemoteOverlayShare(service,overlay,sprite_cache=ROOT/'sprite-cache')
    share.layout=layout
    server=TrackerHTTPServer(('127.0.0.1',0),
        make_handler(service,secrets.token_urlsafe(32),companion,layout=layout,
                     profile=args.profile or 'principal',overlay=overlay,share=share,
                     sprite_cache=ROOT/'sprite-cache'))
    worker=threading.Thread(target=service.run,daemon=True);worker.start()
    url=f'http://127.0.0.1:{server.server_port}/';print('Tracker local: '+url+'\nPerfil: '+(args.profile or 'principal')+'\nMantén esta ventana abierta. Ctrl+C para cerrar.')
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        service.stop.set()
        with service.condition:service.condition.notify_all()
        worker.join(timeout=5)
        service.flush_state(force=True)  # last coalesced state.json write
        share.close();layout.close();companion.close();server.server_close();diaglog.close()
if __name__=='__main__':main()
