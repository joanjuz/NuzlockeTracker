"""Soul Link metadata never persists full remote views. Resume secrets are separate."""
from __future__ import annotations

import ctypes
import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .direct import SECRET_RE, private_address
from .room import MAX_ROOM_BYTES, identifier
from .room_storage import RoomStorage
from .soul_room import soul_view
from .snapshot import JSONDict, SUPPORTED_GAMES


def _dpapi(raw: bytes, decrypt: bool = False) -> bytes:
    """Windows CurrentUser protection; no machine-wide key or custom cipher."""
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_uint32), ('data', ctypes.c_void_p)]
    buffer = ctypes.create_string_buffer(raw)
    source, target = Blob(len(raw), ctypes.cast(buffer, ctypes.c_void_p)), Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(Blob)]
    function.restype = ctypes.c_int
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError('No se pudo proteger la conexión guardada de este usuario')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


class SoulStorage(RoomStorage):
    def __init__(self, directory: Path) -> None:
        legacy = RoomStorage(directory)
        self.path = directory / 'companion-soul.json'
        self.credentials_path = directory / 'soul-connection.bin'
        self.error = legacy.error
        self.credential_error = ''
        self.data: JSONDict = {'version': 1, 'player_id': legacy.data['player_id'],
                              'runs': dict(legacy.data['runs']), 'room': None}
        if self.path.exists():
            try:
                if self.path.stat().st_size > MAX_ROOM_BYTES:
                    raise ValueError()
                value = json.loads(self.path.read_text(encoding='utf-8'))
                if type(value.get('version')) is not int or value['version'] != 1 or not isinstance(value.get('runs'), dict):
                    raise ValueError()
                if any(game not in SUPPORTED_GAMES for game in value['runs']):
                    raise ValueError()
                self.data = {'version': 1, 'player_id': identifier(value.get('player_id')),
                             'runs': {g: identifier(r) for g, r in value['runs'].items()},
                             'room': soul_view(value['room'], offline=True) if value.get('room') is not None else None}
                self.error = ''
            except (ValueError, TypeError, AttributeError, KeyError, OSError, RecursionError):
                self.error = 'No se pudo recuperar Soul Link; conserva su archivo para recuperar la identidad'

    def cache(self, value: object) -> None:
        if self.error:
            raise ValueError(self.error)
        self.data['room'] = soul_view(value, offline=True)
        self._save()

    def retire_membership(self) -> None:
        self.clear_credentials()
        if self.error:
            raise ValueError(self.error)
        self.data['player_id'] = str(uuid.uuid4())
        self.data['room'] = None
        self._save()

    def credentials(self) -> JSONDict | None:
        if not self.credentials_path.exists():
            return None
        try:
            if self.credentials_path.stat().st_size > 16_384:
                raise ValueError()
            raw = self.credentials_path.read_bytes()
            if os.name == 'nt':
                if not raw.startswith(b'SL3D'):
                    raise ValueError()
                raw = _dpapi(raw[4:], decrypt=True)
            else:
                if not raw.startswith(b'SL3P'):
                    raise ValueError()
                raw = raw[4:]
            value = json.loads(raw)
            if not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1:
                raise ValueError()
            parts = urlsplit(value['base'])
            address = private_address(parts.hostname)
            if (parts.scheme != 'http' or parts.netloc != f'{address}:{parts.port}' or not parts.port
                    or parts.path or parts.query or parts.fragment):
                raise ValueError()
            for key in ('session_id', 'epoch', 'player_id', 'run_id'):
                identifier(value.get(key))
            if value.get('game') not in SUPPORTED_GAMES or not SECRET_RE.fullmatch(value.get('token', '')):
                raise ValueError()
            return {k: value[k] for k in ('base', 'session_id', 'epoch', 'player_id', 'run_id', 'game', 'token')}
        except (ValueError, TypeError, AttributeError, KeyError, OSError, RecursionError):
            self.credential_error = 'La conexión guardada no puede recuperarse; usa Salir para olvidarla'
            return None

    def save_credentials(self, base: str, token: str, person: JSONDict, view: JSONDict) -> None:
        value = {'version': 1, 'base': base, 'token': token, 'session_id': view['session_id'],
                 'epoch': view['epoch'], **{k: person[k] for k in ('player_id', 'run_id', 'game')}}
        raw = json.dumps(value, separators=(',', ':')).encode()
        raw = b'SL3D' + _dpapi(raw) if os.name == 'nt' else b'SL3P' + raw
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.credentials_path.with_suffix('.tmp')
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                if os.name != 'nt':
                    os.fchmod(handle.fileno(), 0o600)
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.credentials_path)
        finally:
            temporary.unlink(missing_ok=True)

    def clear_credentials(self) -> None:
        self.credentials_path.unlink(missing_ok=True)
        self.credential_error = ''
