"""Per-profile opt-in room lifecycle. No listener or credentials survive restart."""
from __future__ import annotations

import copy
import threading
import time
from pathlib import Path
from typing import Protocol

from .direct import identity
from .room_links import captures, links
from .room import MAX_SEQUENCE, room_view
from .room_direct import RoomHost, RoomPeer
from .room_storage import RoomStorage
from .snapshot import JSONDict, snapshot


class SnapshotService(Protocol):
    def snapshot(self) -> JSONDict: ...


class RoomSync:
    def __init__(self, service: SnapshotService, directory: Path) -> None:
        self.service = service
        self.storage = RoomStorage(directory)
        self.lock = threading.RLock()
        self.host: RoomHost | None = None
        self.peer: RoomPeer | None = None
        self.person: JSONDict = {}
        self.view: JSONDict | None = self.storage.data['room']
        self.sequence = 0
        self.links: dict[str, str] = {}
        self.error = self.storage.error
        self.last_sync = 0.0
        self.last_cache = 0.0

    @property
    def active(self) -> bool:
        return self.host is not None or self.peer is not None

    def start(self, action: str, options: JSONDict) -> None:
        with self.lock:
            if self.active:
                raise ValueError('Sal de la sala antes de cambiar de conexión')
            name, game = identity(options.get('name'), options.get('game'))
            person = self.storage.identity(name, game)
            if action == 'room_host':
                try:
                    self.host = RoomHost(options.get('host', '127.0.0.1'), options.get('port', 8770),
                                         person, options.get('capacity', 4))
                except OSError:
                    raise ValueError('No se pudo abrir la sala; revisa IP y puerto') from None
                self.view = self.host.room_status()
            elif action == 'room_join':
                self.peer = RoomPeer(options.get('invite_code'), person)
                self.view = self.peer.view
            else:
                raise ValueError('Acción de sala inválida')
            self.person = person
            self.links = next((m.get('links', {}) for m in self.view['members'] if m['player_id'] == person['player_id']), {})
            self.sequence = 0
            self.last_sync = 0.0
            self.error = ''
        self.sync(force=True)

    def _envelope(self, value: JSONDict | None) -> JSONDict:
        if self.view is None:
            raise ValueError('Sala no disponible')
        if self.sequence >= MAX_SEQUENCE:
            raise ValueError('Secuencia agotada; crea otra sesión')
        self.sequence += 1
        return {'protocol': 2, 'session_id': self.view['session_id'], 'epoch': self.view['epoch'],
                'run_id': self.person['run_id'], 'sequence': self.sequence, 'state': value, 'links': self.links}

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
                    raise ValueError('Selecciona el juego de esta sala para compartir')
            except ValueError as error:
                value = None
                local_error = str(error)
            try:
                envelope = self._envelope(value)
                if self.host:
                    self.view = self.host.local_exchange(envelope)
                elif self.peer:
                    self.view = self.peer.exchange(envelope)
                self.error = local_error
                if self.view is not None and (force or now - self.last_cache >= 5):
                    self.storage.cache(self.view)
                    self.last_cache = now
            except (ValueError, OSError) as error:
                self.error = str(error) if isinstance(error, ValueError) else 'No se pudo guardar el estado de sala'
                # Keep the last snapshot for inspection but never present a
                # successful old heartbeat after a failed network exchange.
                if self.view is not None:
                    self.view = room_view(self.view, offline=True)

    def status(self) -> JSONDict:
        with self.lock:
            if self.host:
                self.view = self.host.room_status()
            invite = ''
            if self.host:
                with self.host.lock:
                    if any(deadline > self.host.room.clock() for deadline, _ in self.host.room.invites.values()):
                        invite = self.host.link
            return {'configured': self.active, 'protocol': 2, 'transport': 'direct',
                    'direct_role': 'host' if self.host else 'join',
                    'host_address': self.host.address if self.host else '',
                    'my_name': self.person.get('name', ''), 'game': self.person.get('game', ''),
                    'player_id': self.storage.data['player_id'], 'room': copy.deepcopy(self.view),
                    'partner': None, 'invite_link': invite, 'invite_code': invite,
                    'error': self.error}

    def manage(self, action: str, options: JSONDict) -> None:
        with self.lock:
            if action == 'room_new_run':
                if self.active:
                    raise ValueError('Sal de la sala antes de comenzar otra partida')
                self.storage.new_run(options.get('game', ''))
                self.view = None
                return
            if action == 'room_link':
                if not self.active:
                    raise ValueError('Conecta la sala antes de elegir una captura')
                route, key = options.get('route'), options.get('pokemon_key')
                proposed = dict(self.links)
                if not isinstance(route, str):
                    raise ValueError('Ruta inválida')
                if key is None:
                    proposed.pop(route, None)
                else:
                    proposed[route] = key
                proposed = links(proposed, self.person['game'])
                if key is not None:
                    current = snapshot(self.service.snapshot())
                    if current['game'] != self.person['game'] or key not in captures(self.person['game'], current).get(route, set()):
                        raise ValueError('Elige una captura actual de tu propia ruta')
                self.links = proposed
                self.sync(force=True)
                return
            if not self.host:
                raise ValueError('Esta acción corresponde al anfitrión')
            with self.host.lock:
                pid = options.get('player_id')
                if action == 'room_invite':
                    if pid is not None and not isinstance(pid, str):
                        raise ValueError('Jugador inválido')
                    self.host.new_invitation(pid)
                elif action == 'room_revoke':
                    self.host.room.revoke_invites()
                elif action == 'room_remove':
                    if not isinstance(pid, str):
                        raise ValueError('Jugador inválido')
                    self.host.room.remove(pid)
                else:
                    raise ValueError('Acción de sala inválida')
            self.view = self.host.room_status()
            self.storage.cache(self.view)

    def validate_confirmation(self, context: object, key: object) -> None:
        """Bind an explicitly clicked local command to the still-current room/run."""
        with self.lock:
            if not self.active or self.view is None or not isinstance(context, dict):
                raise ValueError('Este aviso ya no corresponde a una sala activa')
            if self.host:
                self.view = self.host.room_status()
            if (context.get('session_id') != self.view['session_id']
                    or context.get('epoch') != self.view['epoch']
                    or context.get('local_run_id') != self.person['run_id']
                    or self.service.snapshot().get('game') != self.person['game']):
                raise ValueError('La sala o la partida cambió; revisa el aviso')
            remote = next((m for m in self.view['members']
                           if m['player_id'] == context.get('player_id')
                           and m['run_id'] == context.get('run_id')), None)
            route, pokemon_key = context.get('route'), context.get('pokemon_key')
            if not isinstance(route, str) or not isinstance(pokemon_key, str):
                raise ValueError('Aviso de ruta inválido')
            if (remote is None or remote['player_id'] == self.person['player_id']
                    or not remote['online'] or not remote['source_live'] or remote['state'] is None
                    or remote['links'].get(route) != pokemon_key or self.links.get(route) != key):
                raise ValueError('El enlace del aviso ya no está disponible')
            death = remote['state']['progress']['deaths'].get(pokemon_key)
            if (not death or death.get('source') == 'soullink-response'
                    or str(death.get('recorded_at', '')) != context.get('recorded_at')):
                raise ValueError('La muerte remota cambió; no se aplicó el aviso')

    def close(self) -> None:
        with self.lock:
            host, peer = self.host, self.peer
            try:
                if peer:
                    peer.exchange(self._envelope(None), leave=True)
            except (ValueError, OSError):
                pass  # Closing locally must work without the host.
            self.host = self.peer = None
            if host:
                host.close()
            if self.view is not None:
                self.view = room_view(self.view, offline=True)
                try:
                    self.storage.cache(self.view)
                except (ValueError, OSError):
                    pass
