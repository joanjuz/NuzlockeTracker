"""Soul Link lifecycle with explicit full-view permission and private remote caches."""
from __future__ import annotations

import copy
import threading
import time
from pathlib import Path

from .direct import identity
from .room import MAX_SEQUENCE
from .room_links import captures, links
from .room_sync import SnapshotService
from .soul_direct import SoulHost, SoulPeer, default_host
from .soul_room import PROTOCOL, soul_from_snapshot, soul_view
from .soul_storage import SoulStorage
from .snapshot import JSONDict, snapshot


class SoulSync:
    def __init__(self, service: SnapshotService, directory: Path) -> None:
        self.service = service
        self.storage = SoulStorage(directory)
        self.lock = threading.RLock()
        self.host: SoulHost | None = None
        self.peer: SoulPeer | None = None
        self.person: JSONDict = {}
        self.links: dict[str, str] = {}
        self.sharing = False
        self.view: JSONDict | None = self.storage.data['room']
        self.own_soul: JSONDict = {'captures': {}, 'missed_routes': []}
        self.sequence = 0
        self.error = self.storage.error
        self.last_sync = 0.0
        self.received_at = 0.0
        self.last_cache = 0.0
        self.needs_forget = False

    @property
    def active(self) -> bool:
        return self.host is not None or self.peer is not None

    @property
    def present(self) -> bool:
        return self.storage.path.exists() or self.storage.credentials_path.exists() or bool(self.error)

    def start(self, action: str, options: JSONDict) -> None:
        with self.lock:
            if self.active:
                raise ValueError('Ya estás en Soul Link; sal antes de abrir otra sala')
            name, game = identity(options.get('name'), options.get('game'))
            person = self.storage.identity(name, game)
            self.sharing = False
            if action == 'soul_host':
                try:
                    new_host = SoulHost(options.get('host') or default_host(), options.get('port', 8770), person)
                except OSError:
                    raise ValueError('No se pudo crear la sala; revisa la dirección y el puerto en opciones avanzadas') from None
                try:
                    self.storage.clear_credentials()
                except OSError:
                    new_host.close()
                    raise ValueError('No se pudo preparar la conexión; conserva tu conexión guardada') from None
                self.host = new_host
                self.view = self.host.room_status()
            elif action == 'soul_join':
                self.peer = SoulPeer(options.get('invite_code'), person, self.storage.credentials())
                self.view = self.peer.view
                try:
                    self.storage.save_credentials(self.peer.base, self.peer.token, person, self.view)
                except (ValueError, OSError):
                    # Release an admission whose ownership proof could not be saved.
                    self.person, self.sequence = person, 0
                    try:
                        self.peer.exchange(self._envelope(None), leave=True)
                    except (ValueError, OSError):
                        pass
                    finally:
                        self._purge_views()
                        self.peer = None
                    self.needs_forget = True
                    self.error = 'No se pudo guardar tu conexión. Usa Salir para olvidar el intento y entrar de nuevo'
                    raise ValueError(self.error) from None
            else:
                raise ValueError('Acción de Soul Link inválida')
            self.person = person
            own = next(m for m in self.view['members'] if m['player_id'] == person['player_id'])
            self.links = dict(own['links'])
            self.own_soul = copy.deepcopy(own['soul'])
            self.sequence = 0
            self.received_at = time.monotonic()
            self.last_sync = 0.0
            self.error = ''
            self.needs_forget = False
        self.sync(force=True)

    def _envelope(self, value: JSONDict | None) -> JSONDict:
        if self.view is None or self.sequence >= MAX_SEQUENCE:
            raise ValueError('La sala debe conectarse de nuevo')
        self.sequence += 1
        self.own_soul = soul_from_snapshot(value, self.links, self.own_soul)
        return {'protocol': PROTOCOL, 'session_id': self.view['session_id'], 'epoch': self.view['epoch'],
                'run_id': self.person['run_id'], 'sequence': self.sequence, 'sharing': self.sharing,
                'source_live': value is not None, 'state': value if self.sharing else None,
                'links': dict(self.links), 'soul': self.own_soul}

    def _purge_views(self) -> None:
        if self.view is not None:
            self.view = soul_view(self.view, offline=True)
        if self.peer:
            self.peer.view = soul_view(self.peer.view, offline=True)

    def sync(self, *, force: bool = False) -> None:
        with self.lock:
            now = time.monotonic()
            if not self.active or (not force and now - self.last_sync < 1):
                return
            self.last_sync = now
            local_error = ''
            try:
                value = snapshot(self.service.snapshot())
                if value['game'] != self.person['game']:
                    raise ValueError('Selecciona el juego de esta sala para continuar Soul Link')
            except ValueError as error:
                value = None
                local_error = str(error)
            try:
                envelope = self._envelope(value)
                started = time.monotonic()
                if self.host:
                    view = self.host.local_exchange(envelope)
                elif self.peer:
                    view = self.peer.exchange(envelope)
                else:
                    return
                finished = time.monotonic()
                self.view = soul_view(view)
                elapsed = int((finished - started) * 1000)
                for m in self.view['members']:
                    m['view_ttl_ms'] = max(0, m['view_ttl_ms'] - elapsed)
                    if not m['view_ttl_ms']:
                        m['state'] = None
                self.received_at = finished
                self.error = local_error
                if force or now - self.last_cache >= 5:
                    self.storage.cache(self.view)
                    self.last_cache = now
            except (ValueError, OSError) as error:
                self.error = str(error) if isinstance(error, ValueError) else 'No se pudo guardar el estado de Soul Link'
                self._purge_views()

    def status(self) -> JSONDict:
        with self.lock:
            if self.host:
                self.view = self.host.room_status()
                self.received_at = time.monotonic()
            current_view = self.view
            if not self.host and self.view is not None:
                # Decrease from the same authoritative receipt, never from UI polling.
                elapsed = max(0, int((time.monotonic() - self.received_at) * 1000))
                view = copy.deepcopy(self.view)
                for member in view['members']:
                    member['view_ttl_ms'] = max(0, member['view_ttl_ms'] - elapsed)
                    if not member['view_ttl_ms']:
                        member['state'] = None
                current_view = view
                for original, reduced in zip(self.view['members'], view['members']):
                    if not reduced['view_ttl_ms']:
                        original['state'] = None
                        original['view_ttl_ms'] = 0
                    if elapsed >= 20_000:
                        reduced['online'] = reduced['source_live'] = False
                if self.peer:
                    self.peer.view = copy.deepcopy(view)
            return {'configured': self.active, 'protocol': PROTOCOL, 'transport': 'direct',
                    'direct_role': 'host' if self.host else 'join',
                    'host_address': self.host.address if self.host else '',
                    'my_name': self.person.get('name', ''), 'game': self.person.get('game', ''),
                    'player_id': self.storage.data['player_id'], 'room': copy.deepcopy(current_view),
                    'own_sharing': self.sharing if self.active else False,
                    'can_resume': self.storage.credentials_path.exists(),
                    'can_forget': self.needs_forget or self.storage.credentials_path.exists(),
                    'partner': None, 'invite_link': self.host.link() if self.host else '',
                    'invite_code': self.host.link() if self.host else '', 'error': self.error}

    def manage(self, action: str, options: JSONDict) -> None:
        with self.lock:
            if action == 'soul_new_run':
                if self.active:
                    raise ValueError('Sal de la sala antes de usar otro reto')
                self.storage.retire_membership()
                self.storage.new_run(options.get('game', ''))
                self.view = None
                return
            if not self.active:
                raise ValueError('Conéctate a Soul Link antes de usar esta acción')
            if action == 'soul_share':
                sharing = options.get('sharing')
                if type(sharing) is not bool:
                    raise ValueError('El permiso de compartir debe estar activado o desactivado')
                self.sharing = sharing
                if not sharing:
                    for view in (self.view, self.peer.view if self.peer else None):
                        if view:
                            for m in view['members']:
                                if m['player_id'] == self.person['player_id']:
                                    m.update(state=None, sharing=False, view_ttl_ms=0)
                self.sync(force=True)
                return
            if action == 'soul_link':
                route, key = options.get('route'), options.get('pokemon_key')
                if not isinstance(route, str):
                    raise ValueError('Ruta inválida')
                proposed = dict(self.links)
                if key is None:
                    proposed.pop(route, None)
                else:
                    proposed[route] = key
                proposed = links(proposed, self.person['game'])
                if key is not None:
                    current = snapshot(self.service.snapshot())
                    if current['game'] != self.person['game'] or key not in captures(current['game'], current).get(route, set()):
                        raise ValueError('Elige una captura actual de tu propia ruta')
                self.links = proposed
                self.sync(force=True)
                return
            if not self.host:
                raise ValueError('Solo quien creó la sala administra su invitación y plazas')
            with self.host.lock:
                if action == 'soul_invite':
                    self.host.room.invite()
                elif action == 'soul_revoke':
                    self.host.room.revoke_invites()
                elif action == 'soul_remove':
                    self.host.room.remove(options.get('player_id', ''))
                else:
                    raise ValueError('Acción de Soul Link inválida')
            self.view = self.host.room_status()
            self.storage.cache(self.view)

    def validate_confirmation(self, context: object, key: object) -> None:
        with self.lock:
            if not self.active or not isinstance(context, dict) or context.get('protocol') != PROTOCOL:
                raise ValueError('El aviso ya no corresponde a Soul Link activo')
            view = self.status()['room']
            if (view is None or context.get('session_id') != view['session_id']
                    or context.get('epoch') != view['epoch'] or context.get('local_run_id') != self.person['run_id']
                    or self.service.snapshot().get('game') != self.person['game']):
                raise ValueError('La sala o partida cambió; revisa el aviso')
            remote = next((m for m in view['members'] if m['player_id'] == context.get('player_id')
                           and m['run_id'] == context.get('run_id')), None)
            route = context.get('route')
            if not isinstance(route, str) or not remote or not remote['online'] or not remote['source_live']:
                raise ValueError('La captura remota no está disponible')
            record = remote['soul']['captures'].get(route)
            if (not record or record['key'] != context.get('pokemon_key') or record['status'] != 'dead'
                    or record['death_at'] != context.get('recorded_at') or record['response']
                    or self.links.get(route) != key or remote['player_id'] == self.person['player_id']):
                raise ValueError('El enlace o la muerte remota cambió; no se aplicó el aviso')

    def leave(self) -> None:
        with self.lock:
            self.sharing = False
            if self.peer:
                try:
                    self.peer.exchange(self._envelope(None), leave=True)
                except (ValueError, OSError):
                    # Explicitly forgetting an unreachable connection cannot revoke
                    # a remote reserved slot; host can free it. It never transfers ID.
                    pass
            self.close()
            self.storage.retire_membership()
            self.person, self.view, self.links = {}, None, {}
            self.needs_forget = False
            self.error = ''

    def close(self) -> None:
        """App shutdown reserves guest ownership; only explicit leave releases it."""
        with self.lock:
            host = self.host
            self.host = self.peer = None
            self.sharing = False
            if host:
                host.close()
            self._purge_views()
            if self.view is not None:
                try:
                    self.storage.cache(self.view)
                except (ValueError, OSError):
                    pass
