"""Per-profile room identity and read-only cache, without network credentials."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from .room import MAX_ROOM_BYTES, identifier, room_view
from .snapshot import JSONDict, SUPPORTED_GAMES


class RoomStorage:
    def __init__(self, directory: Path) -> None:
        self.path = directory / 'companion-multiplayer.json'
        self.data: JSONDict = {'version': 1, 'player_id': str(uuid.uuid4()), 'runs': {}, 'room': None}
        self.error = ''
        if self.path.exists():
            try:
                if self.path.stat().st_size > MAX_ROOM_BYTES + 4096:
                    raise ValueError()
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
                    raise ValueError()
                runs = data.get('runs')
                if not isinstance(runs, dict) or any(k not in SUPPORTED_GAMES for k in runs):
                    raise ValueError()
                self.data = {'version': 1, 'player_id': identifier(data.get('player_id')),
                             'runs': {k: identifier(v) for k, v in runs.items()},
                             'room': room_view(data['room'], offline=True) if data.get('room') is not None else None}
            except (ValueError, TypeError, KeyError, OSError, RecursionError):
                self.error = 'No se pudo leer la identidad multijugador; conserva el archivo para recuperarla'

    def identity(self, name: str, game: str) -> JSONDict:
        if self.error:
            raise ValueError(self.error)
        if game not in SUPPORTED_GAMES:
            raise ValueError('Juego no compatible')
        if game not in self.data['runs']:
            self.data['runs'][game] = str(uuid.uuid4())
            self._save()
        return {'player_id': self.data['player_id'], 'run_id': self.data['runs'][game],
                'name': name, 'game': game}

    def new_run(self, game: str) -> None:
        if self.error or game not in SUPPORTED_GAMES:
            raise ValueError(self.error or 'Juego no compatible')
        self.data['runs'][game] = str(uuid.uuid4())
        self.data['room'] = None
        self._save()

    def cache(self, value: object) -> None:
        if self.error:
            raise ValueError(self.error)
        clean = room_view(value, offline=True)
        self.data['room'] = clean
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        try:
            with temporary.open('w', encoding='utf-8') as handle:
                try:
                    os.chmod(temporary, 0o600)
                except OSError:
                    pass
                json.dump(self.data, handle, ensure_ascii=False, separators=(',', ':'))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
