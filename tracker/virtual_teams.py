"""Saved virtual teams of one run and one game.

A virtual team is a named list of up to six owned Pokémon, kept only on this
computer. It is never sent to Soul Link, OBS or any network service, and it
never changes the party in the game. Members are identified by the same key
the tracker uses for deaths (``origin_version:encryption_constant``); species
and nickname are stored only to name a member that can no longer be found.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MAX_TEAMS = 50
MAX_MEMBERS = 6
MAX_NAME = 60
MAX_TEXT = 40
MAX_BYTES = 200_000
REQUEST_LIMIT = 8192
MEMBER_ID = re.compile(r'\d{1,3}:\d{1,10}')
TEAM_ID = re.compile(r'[0-9a-f]{16}')
NEWER = ('Estos equipos se guardaron con una versión más nueva de Progressive Tracker. '
         'Se conservan sin cambios; actualiza el Tracker para usarlos.')
UNRECOVERED = ('No se pudo conservar una copia del archivo de equipos dañado. '
               'El original sigue intacto y no se permiten cambios; comprueba los permisos y vuelve a abrir la partida.')


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: Any, maximum: int) -> str:
    """Printable text without control characters, trimmed to ``maximum``."""
    if not isinstance(value, str):
        return ''
    return ''.join(ch for ch in value if ch.isprintable()).strip()[:maximum]


def valid_name(value: Any) -> str:
    name = _text(value, MAX_NAME + 1)
    if not name or len(name) > MAX_NAME:
        raise ValueError(f'El nombre del equipo debe tener entre 1 y {MAX_NAME} caracteres')
    return name


def valid_members(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_MEMBERS:
        raise ValueError(f'Un equipo virtual tiene entre 1 y {MAX_MEMBERS} integrantes')
    members: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('Integrante inválido')
        ident = item.get('id')
        if not isinstance(ident, str) or not MEMBER_ID.fullmatch(ident):
            raise ValueError('Identificador de Pokémon inválido')
        if ident in seen:
            raise ValueError('Un mismo Pokémon no puede estar dos veces en el equipo')
        seen.add(ident)
        species_id = item.get('species_id')
        if type(species_id) is not int or not 0 <= species_id <= 65535:
            raise ValueError('Especie inválida')
        members.append({'id': ident, 'species_id': species_id,
                        'species': _text(item.get('species'), MAX_TEXT),
                        'nickname': _text(item.get('nickname'), MAX_TEXT)})
    return members


def _valid_team(team: Any) -> dict[str, Any]:
    """A stored team, validated as strictly as a new one."""
    if not isinstance(team, dict) or not isinstance(team.get('id'), str) or not TEAM_ID.fullmatch(team['id']):
        raise ValueError('Equipo guardado inválido')
    result = {'id': team['id'], 'name': valid_name(team.get('name')), 'members': valid_members(team.get('members'))}
    for field, limit in (('created', 40), ('modified', 40), ('game', 40), ('run', 80)):
        result[field] = _text(team.get(field), limit)
    return result


class VirtualTeamStore:
    """JSON file with the virtual teams of one run and game; every change is written at once."""

    def __init__(self, path: str | os.PathLike[str], game: str, run: str = '') -> None:
        self.path = Path(path)
        self.game = game
        self.run = _text(run, 80)
        self.lock = threading.Lock()
        self.teams: list[dict[str, Any]] = []
        # 'newer': written by a later version, kept untouched and read-only.
        # 'recovered': the file was unreadable and was set aside.
        self.problem: str | None = None
        self._load()

    def _load(self) -> None:
        try:
            if not self.path.is_file():
                return
            if self.path.stat().st_size > MAX_BYTES:
                raise ValueError('Archivo demasiado grande')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or type(data.get('schema_version')) is not int:
                raise ValueError('Formato desconocido')
            if data['schema_version'] > SCHEMA_VERSION:
                self.problem = 'newer'
                return
            teams = data.get('teams')
            if data['schema_version'] != SCHEMA_VERSION or not isinstance(teams, list) or len(teams) > MAX_TEAMS:
                raise ValueError('Formato desconocido')
            loaded = [_valid_team(team) for team in teams]
            if len({team['id'] for team in loaded}) != len(loaded):
                raise ValueError('Equipos repetidos')
            self.teams = loaded
        except (OSError, ValueError, TypeError):
            # Never start from a damaged file, and never overwrite it: keep a copy aside.
            self.problem = 'recovered'
            backup = None
            try:
                # Reserve a unique destination; never replace a previous recovery copy.
                descriptor, name = tempfile.mkstemp(prefix=self.path.name + '.corrupt-', dir=self.path.parent)
                backup = Path(name)
                os.close(descriptor)
                os.replace(self.path, backup)
            except OSError:
                self.problem = 'unrecovered'
                if backup is not None:
                    try:
                        backup.unlink(missing_ok=True)
                    except OSError:
                        pass

    def view(self) -> dict[str, Any]:
        with self.lock:
            return self._view()

    def _view(self) -> dict[str, Any]:
        result: dict[str, Any] = {'schema_version': SCHEMA_VERSION, 'game': self.game,
                                  'teams': json.loads(json.dumps(self.teams)), 'limit': MAX_TEAMS}
        if self.problem == 'newer':
            result['read_only'] = True
            result['notice'] = NEWER
        elif self.problem == 'unrecovered':
            result['read_only'] = True
            result['notice'] = UNRECOVERED
        elif self.problem == 'recovered':
            result['notice'] = ('El archivo de equipos guardados estaba dañado. Se apartó una copia '
                                'y se empezó una lista nueva.')
        return result

    def _write(self, teams: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.tmp')
        temporary.write_text(json.dumps({'schema_version': SCHEMA_VERSION, 'game': self.game, 'teams': teams},
                                        ensure_ascii=False), encoding='utf-8')
        os.replace(temporary, self.path)
        self.teams = teams

    def _find(self, teams: list[dict[str, Any]], ident: Any) -> dict[str, Any]:
        for team in teams:
            if team['id'] == ident:
                return team
        raise ValueError('Ese equipo ya no existe')

    def _free_name(self, teams: list[dict[str, Any]], name: str, skip: str | None = None) -> None:
        if any(team['name'].casefold() == name.casefold() and team['id'] != skip for team in teams):
            raise ValueError('Ya hay un equipo guardado con ese nombre')

    def apply(self, request: Any) -> dict[str, Any]:
        """save | rename | duplicate | delete. Raises ValueError for anything invalid; OSError if the disk fails."""
        if not isinstance(request, dict):
            raise ValueError('Solicitud inválida')
        action = request.get('action')
        with self.lock:
            if self.problem == 'newer':
                raise ValueError(NEWER)
            if self.problem == 'unrecovered':
                raise ValueError(UNRECOVERED)
            teams = json.loads(json.dumps(self.teams))
            stamp = _now()
            if action == 'save':
                name, members = valid_name(request.get('name')), valid_members(request.get('members'))
                ident = request.get('id')
                if ident is None:
                    if len(teams) >= MAX_TEAMS:
                        raise ValueError(f'Se alcanzó el máximo de {MAX_TEAMS} equipos guardados')
                    self._free_name(teams, name)
                    team = {'id': secrets.token_hex(8), 'name': name, 'members': members, 'created': stamp,
                            'modified': stamp, 'game': self.game, 'run': self.run}
                    teams.append(team)
                else:
                    team = self._find(teams, ident)
                    self._free_name(teams, name, team['id'])
                    team.update(name=name, members=members, modified=stamp)
            elif action == 'rename':
                team = self._find(teams, request.get('id'))
                name = valid_name(request.get('name'))
                self._free_name(teams, name, team['id'])
                team.update(name=name, modified=stamp)
            elif action == 'duplicate':
                source = self._find(teams, request.get('id'))
                if len(teams) >= MAX_TEAMS:
                    raise ValueError(f'Se alcanzó el máximo de {MAX_TEAMS} equipos guardados')
                taken = {item['name'].casefold() for item in teams}
                base = source['name'][:MAX_NAME - 12]
                name = next(candidate for candidate in
                            (f'{base} (copia)' if n == 1 else f'{base} (copia {n})' for n in range(1, MAX_TEAMS + 2))
                            if candidate.casefold() not in taken)
                team = {**source, 'id': secrets.token_hex(8), 'name': name, 'created': stamp, 'modified': stamp}
                teams.append(team)
            elif action == 'delete':
                if request.get('confirm') is not True:
                    raise ValueError('Eliminar un equipo requiere confirmación')
                team = self._find(teams, request.get('id'))
                teams.remove(team)
            else:
                raise ValueError('Acción inválida')
            self._write(teams)
            self.problem = None
            result = self._view()
            result['team'] = None if action == 'delete' else team['id']
            return result
