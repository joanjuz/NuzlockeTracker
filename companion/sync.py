"""Local background bridge to a D1-backed HTTPS Worker. Secrets stay in runtime/."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .snapshot import snapshot, viewer_state

# Only the public endpoint is preconfigured, never the administrative CREATE_KEY.
DEFAULT_WORKER_URL = 'https://pokemon-tracker-companion.pokemon-tracker.workers.dev'


def validate_worker_url(url):
    if not isinstance(url, str):
        raise ValueError('Introduce la URL HTTPS de Cloudflare Worker')
    parts = urlsplit(url.strip())
    if (parts.scheme != 'https' or not parts.hostname or not parts.hostname.endswith('.workers.dev')
            or parts.hostname == 'workers.dev' or parts.port not in (None, 443)
            or parts.username or parts.password or parts.path not in ('', '/') or parts.query or parts.fragment):
        raise ValueError('Usa una URL HTTPS *.workers.dev sin rutas, parámetros ni claves')
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        pass
    else:
        raise ValueError('No se permiten direcciones IP')
    return 'https://' + parts.hostname.lower()


def fetch_json(url, method='GET', payload=None, token=None, setup_key=None):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
    # Cloudflare workers.dev may reject urllib's default Python-urllib User-Agent.
    # Mozilla/5.0 is the value verified to work against our public /health endpoint.
    headers = {'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if setup_key:
        headers['X-Setup-Key'] = setup_key
    request = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read(850_000)
            if response.status not in (200, 201):
                raise ValueError('Error HTTP del servicio: ' + str(response.status))
            return json.loads(raw)
    except HTTPError as error:
        try:
            details = json.loads(error.read(1024)).get('error', 'Error de la nube')
        except (ValueError, UnicodeError):
            details = 'Error de la nube'
        raise ValueError(f'{details} (HTTP {error.code})') from None
    except (URLError, TimeoutError, OSError) as error:
        raise ValueError('No se pudo contactar Cloudflare; revisa Internet y la URL') from error


class CompanionSync:
    def __init__(self, service, directory, transport=fetch_json):
        self.service = service
        self.directory = Path(directory)
        self.settings_path = self.directory / 'companion-credentials.json'
        self.cache_path = self.directory / 'companion-cache.json'
        self.transport = transport
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.thread = None
        self.settings = {}
        self.partner = None
        self.error = ''
        self.last_uploaded_hash = None
        self.last_core_hash = None
        self.last_upload_at = 0.0
        if self.settings_path.is_file():
            try:
                settings = json.loads(self.settings_path.read_text(encoding='utf-8'))
                if validate_worker_url(settings.get('worker_url')) and isinstance(settings.get('token'), str):
                    self.settings = settings
            except (ValueError, OSError):
                self.error = 'No se pudo recuperar la configuración de compañero'
        if self.cache_path.is_file():
            try:
                data = json.loads(self.cache_path.read_text(encoding='utf-8'))
                if data.get('partner') and data['partner'].get('state'):
                    viewer_state(data['partner']['state'])
                self.partner = data.get('partner')
            except (ValueError, OSError, KeyError):
                pass

    def _store(self, path, data):
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        with open(tmp, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, separators=(',', ':'))
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)

    def default_worker_url(self):
        # A second profile may inherit the public address, never private tokens.
        principal = self.directory.parent.parent if self.directory.parent.name == 'profiles' else self.directory
        path = principal / 'companion-credentials.json'
        if path.is_file():
            try:
                info = json.loads(path.read_text(encoding='utf-8'))
                return validate_worker_url(info.get('worker_url'))
            except (ValueError, OSError):
                pass
        return DEFAULT_WORKER_URL

    def status(self):
        with self.lock:
            worker_url = self.settings.get('worker_url') or self.default_worker_url()
            invite = self.settings.get('invite_code', '')
            return {'configured': bool(self.settings),
                    'worker_url': self.settings.get('worker_url', ''),
                    'default_worker_url': worker_url,
                    'invite_link': worker_url + '/join#' + invite if invite else '',
                    'my_name': self.settings.get('name', ''),
                    'game': self.settings.get('game', ''),
                    'invite_code': self.settings.get('invite_code', ''),
                    'partner': self.partner,
                    'error': self.error}

    def _create_or_join(self, action, options):
        invite = options.get('invite_code', '')
        if not isinstance(invite, str):
            raise ValueError('Código de invitación inválido')
        invite = invite.strip()
        worker_hint = options.get('worker_url') or self.default_worker_url()
        # Full invitations include the public Worker URL and one-use code.
        if action == 'join' and invite.startswith('https://'):
            parts = urlsplit(invite)
            if parts.path != '/join' or parts.query or not parts.fragment:
                raise ValueError('Enlace de invitación inválido')
            worker_hint = parts._replace(path='', query='', fragment='').geturl()
            invite = parts.fragment
        worker_url = validate_worker_url(worker_hint)
        name = options.get('name', '').strip()
        if not 1 <= len(name) <= 32 or any(ord(c) < 32 or c in '<>' for c in name):
            raise ValueError('Escribe un nombre entre 1 y 32 caracteres')
        game = options.get('game')
        if game not in ('Ultra Sun 1.0', 'Ultra Moon 1.0'):
            raise ValueError('Selecciona Ultra Sol o Ultra Luna 1.0')
        if action == 'create':
            setup_key = options.get('setup_key', '')
            if not isinstance(setup_key, str) or len(setup_key) < 16:
                raise ValueError('La clave de creación de Cloudflare debe tener al menos 16 caracteres')
            result = self.transport(worker_url + '/v1/pairs', 'POST', {'name': name, 'game': game}, setup_key=setup_key)
        else:
            if not 12 <= len(invite) <= 100:
                raise ValueError('Introduce el código de invitación completo')
            result = self.transport(worker_url + '/v1/pairs/join', 'POST', {'name': name, 'game': game, 'invite_code': invite})
        if not isinstance(result.get('token'), str) or not isinstance(result.get('pair_id'), str):
            raise ValueError('Respuesta inesperada del servidor')
        new_settings = {'worker_url': worker_url, 'token': result['token'],
                        'pair_id': result['pair_id'], 'name': name, 'game': game,
                        'invite_code': result.get('invite_code', '')}
        with self.lock:
            if self.settings:
                raise ValueError('Ya existe una pareja; desvincúlala primero')
            self._store(self.settings_path, new_settings)
            self.settings = new_settings
            self.partner = None
            self.last_uploaded_hash = None
            self.last_core_hash = None
            self.error = ''
            if self.cache_path.exists():
                self.cache_path.unlink()
            self.wake.set()
        return self.status()

    def perform(self, action, options=None):
        options = options or {}
        if action in ('create', 'join'):
            with self.lock:
                if self.settings:
                    raise ValueError('Ya existe una pareja; desvincúlala primero')
            return self._create_or_join(action, options)
        if action == 'leave':
            with self.lock:
                settings = dict(self.settings)
                if not settings:
                    return self.status()
            # Revoke cloud credential before losing local copy; fail closed on network errors.
            try:
                self.transport(settings['worker_url'] + '/v1/leave', 'POST', {}, token=settings['token'])
            except ValueError as exc:
                # The other player may already have revoked the whole pair.
                if '(HTTP 401)' not in str(exc) and '(HTTP 404)' not in str(exc):
                    raise
            with self.lock:
                self.settings = {}
                self.partner = None
                self.last_uploaded_hash = None
                self.last_core_hash = None
                self.error = ''
                for path in (self.settings_path, self.cache_path):
                    if path.exists():
                        path.unlink()
            return self.status()
        if action == 'refresh':
            self.sync_once(force=True)
            return self.status()
        raise ValueError('Acción de compañero inválida')

    def sync_once(self, force=False):
        with self.lock:
            settings = dict(self.settings)
        if not settings:
            return
        now = time.monotonic()
        try:
            current = self.service.snapshot()
            local = snapshot(current)
            if local['game'] != settings['game']:
                raise ValueError('Selecciona ' + settings['game'] + ' para sincronizar tu partida')
        except ValueError as error:
            # A disconnected tracker must never overwrite the last valid cloud snapshot.
            local = None
            local_error = str(error)
        else:
            local_error = ''
        try:
            if local is not None:
                signature = hashlib.sha256(json.dumps(local, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                # Coalesce box-only updates during the automatic 32-box sweep,
                # but upload HP, party and death changes without waiting.
                core_hash = hashlib.sha256(json.dumps([local['party'], local['progress'], local['battle_hp']], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                scanning = (current.get('scan') or {}).get('active') is True
                with self.lock:
                    should_upload = force or signature != self.last_uploaded_hash or now - self.last_upload_at > 300
                    if scanning and core_hash == self.last_core_hash and not force:
                        should_upload = False
                if should_upload:
                    self.transport(settings['worker_url'] + '/v1/state', 'PUT', {'state': local}, token=settings['token'])
                    with self.lock:
                        if self.settings.get('token') == settings['token']:
                            self.last_uploaded_hash = signature
                            self.last_core_hash = core_hash
                            self.last_upload_at = now
            remote = self.transport(settings['worker_url'] + '/v1/partner', 'GET', token=settings['token'])
            partner = remote.get('partner')
            if partner is not None and partner.get('state') is not None:
                viewer_state(partner['state'])
                with self.lock:
                    self._store(self.cache_path, {'partner': partner})
                    self.partner = partner
            elif partner is not None:
                with self.lock:
                    self.partner = partner
            elif not remote.get('partner_joined'):
                with self.lock:
                    self.partner = None
            with self.lock:
                if self.settings.get('token') == settings['token']:
                    self.error = local_error
                    if remote.get('partner_joined'):
                        self.settings.pop('invite_code', None)
                        self._store(self.settings_path, self.settings)
        except (ValueError, KeyError, OSError) as error:
            with self.lock:
                if self.settings.get('token') == settings['token']:
                    self.error = str(error)

    def start(self):
        if self.thread is not None:
            return
        self.thread = threading.Thread(target=self._run, daemon=True, name='companion-sync')
        self.thread.start()

    def _run(self):
        # Observe local state revisions via TrackerService.condition; poll remote
        # every five seconds even without local changes.
        last_revision = None
        next_poll = 0.0
        while not self.stop.is_set():
            with self.service.condition:
                revision = self.service.state['revision']
                changed = revision != last_revision
                if not changed and not self.wake.is_set() and time.monotonic() < next_poll:
                    self.service.condition.wait(timeout=min(0.5, max(0.0, next_poll - time.monotonic())))
                    continue
                last_revision = revision
            self.wake.clear()
            # Short debounce avoids excessive writes from consecutive RAM reads.
            if changed and self.stop.wait(0.35):
                break
            self.sync_once()
            next_poll = time.monotonic() + 5.0

    def close(self):
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=10)
