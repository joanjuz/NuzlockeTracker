"""Named local runs. Each directory owns all saved tracker and companion data."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path


def acquire_run_lock(home, profile):
    """Hold an OS lock until the returned file closes, including after crashes."""
    if not isinstance(profile, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,31}', profile):
        raise ValueError('Perfil inválido.')
    directory = Path(home) / '.locks'
    directory.mkdir(parents=True, exist_ok=True)
    handle = open(directory / (profile + '.lock'), 'a+b')
    try:
        if sys.platform == 'win32':
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('Esta partida ya está abierta en otra ventana.') from None
    return handle


class RunProfileStore:
    """Directory discovery avoids a shared index that two windows could overwrite."""
    def __init__(self, runtime):
        self.runtime = Path(runtime)

    def directory(self, ident):
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,31}', ident):
            raise ValueError('Perfil inválido.')
        candidate = self.runtime if ident == 'principal' else self.runtime / 'profiles' / ident
        if not candidate.resolve().is_relative_to(self.runtime.resolve()):
            raise ValueError('Carpeta de perfil inválida.')
        return candidate

    def profiles(self):
        ids = ['principal']
        if (self.runtime / 'profiles' / 'segundo-jugador').is_dir() or not (self.runtime / '.second-profile-deleted').exists():
            ids.append('segundo-jugador')
        directory = self.runtime / 'profiles'
        if directory.is_dir():
            ids.extend(sorted(p.name for p in directory.iterdir() if p.is_dir() and p.name not in ids))
        result = []
        for ident in ids:
            try:
                path = self.directory(ident)
            except ValueError:
                continue
            name = {'principal': 'Partida principal', 'segundo-jugador': 'Segundo jugador'}.get(ident, ident)
            try:
                saved = json.loads((path / 'run-profile.json').read_text(encoding='utf-8'))
                name = self.validate_name(saved['name'])
            except (OSError, ValueError, KeyError, TypeError):
                pass
            result.append({'id': ident, 'name': name})
        return result

    @staticmethod
    def validate_name(name):
        if not isinstance(name, str):
            raise ValueError('Escribe un nombre para la partida.')
        name = name.strip()
        if not name or len(name) > 64 or any(ord(c) < 32 for c in name):
            raise ValueError('El nombre debe tener entre 1 y 64 caracteres, sin saltos de línea.')
        return name

    def require(self, ident):
        if ident not in {p['id'] for p in self.profiles()}:
            raise ValueError('La partida seleccionada no existe.')
        return self.directory(ident)

    def delete(self, ident):
        """Delete only an inactive run while excluding other tracker windows."""
        if ident == 'principal':
            raise ValueError('La partida principal no se puede eliminar.')
        target = self.require(ident)
        with acquire_run_lock(self.runtime.parent, ident):
            expected_parent = self.runtime.resolve() / 'profiles'
            resolved = target.resolve()
            if resolved.parent != expected_parent or target.is_symlink():
                raise ValueError('Carpeta de perfil inválida.')
            # Refuse Windows junctions and nested links before recursive removal.
            # Never traverse a folder redirected outside this profile.
            if target.exists():
                for directory, folders, files in os.walk(target, followlinks=False):
                    for item in [Path(directory), *[Path(directory) / p for p in folders + files]]:
                        info = item.lstat()
                        if item.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                            raise ValueError('No se puede eliminar un perfil con enlaces de archivos o carpetas.')
                        if not item.resolve().is_relative_to(resolved):
                            raise ValueError('Carpeta de perfil inválida.')
            if ident == 'segundo-jugador':
                self.runtime.mkdir(parents=True, exist_ok=True)
                (self.runtime / '.second-profile-deleted').touch()
            if target.exists():
                shutil.rmtree(target)

    def create(self, name):
        name = self.validate_name(name)
        if any(p['name'].casefold() == name.casefold() for p in self.profiles()):
            raise ValueError('Ya existe una partida con ese nombre.')
        ident = 'run-' + uuid.uuid4().hex[:24]
        directory = self.directory(ident)
        directory.mkdir(parents=True, exist_ok=False)
        try:
            (directory / 'run-profile.json').write_text(
                json.dumps({'name': name}, ensure_ascii=False), encoding='utf-8')
        except OSError:
            (directory / 'run-profile.json').unlink(missing_ok=True)
            directory.rmdir()
            raise
        return {'id': ident, 'name': name}
