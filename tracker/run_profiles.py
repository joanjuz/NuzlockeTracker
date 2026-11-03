"""Named local runs. Each directory owns all saved tracker and companion data."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path


PROFILE_ID = re.compile(r'[a-z0-9][a-z0-9_-]{0,31}')


def valid_profile_id(value):
    return isinstance(value, str) and PROFILE_ID.fullmatch(value) is not None


def acquire_run_lock(home, profile):
    """Hold an OS lock until the returned file closes, including after crashes."""
    if not valid_profile_id(profile):
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


# The main run keeps its data loose in runtime/ (next to profiles/, the update
# cache, etc.), so deleting it removes ONLY these entries, never the folder.
PRINCIPAL_FILE_PATTERNS = ('state.json', 'state.tmp', 'state-*-progress.json*', 'state-progress.json*',
                           'session-profile.json', 'obs-overlay.json', 'obs-overlay.tmp',
                           'pk3ds-templates.json', 'companion-credentials.json', 'companion-cache.json',
                           'run-profile.json')
PRINCIPAL_DIRS = ('obs-fonts', 'obs-hp-images', 'diagnosticos')
PRINCIPAL_DELETED = '.principal-deleted'


def _is_link(path):
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


class RunProfileStore:
    """Directory discovery avoids a shared index that two windows could overwrite."""
    def __init__(self, runtime):
        self.runtime = Path(runtime)

    def directory(self, ident):
        if not valid_profile_id(ident):
            raise ValueError('Perfil inválido.')
        candidate = self.runtime if ident == 'principal' else self.runtime / 'profiles' / ident
        if not candidate.resolve().is_relative_to(self.runtime.resolve()):
            raise ValueError('Carpeta de perfil inválida.')
        return candidate

    def profiles(self):
        ids = [] if (self.runtime / PRINCIPAL_DELETED).exists() else ['principal']
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

    def principal_entries(self):
        """Files and folders that belong to the main run (see PRINCIPAL_FILE_PATTERNS)."""
        found = []
        for pattern in PRINCIPAL_FILE_PATTERNS:
            found.extend(p for p in self.runtime.glob(pattern) if p.parent == self.runtime)
        found.extend(self.runtime / name for name in PRINCIPAL_DIRS if (self.runtime / name).exists())
        return sorted(set(found))

    def restore_principal(self):
        """The main run is used again (e.g. opened explicitly): list it again."""
        (self.runtime / PRINCIPAL_DELETED).unlink(missing_ok=True)

    def _delete_principal(self):
        self.require('principal')
        with acquire_run_lock(self.runtime.parent, 'principal'):
            entries = self.principal_entries()
            root = self.runtime.resolve()
            # Check everything first: refuse links/junctions before deleting anything.
            for entry in entries:
                if _is_link(entry) or entry.resolve().parent != root:
                    raise ValueError('No se puede eliminar la partida: contiene enlaces de archivos o carpetas.')
                if entry.is_dir():
                    for directory, folders, files in os.walk(entry, followlinks=False):
                        for item in [Path(directory) / n for n in folders + files]:
                            if _is_link(item) or not item.resolve().is_relative_to(entry.resolve()):
                                raise ValueError('No se puede eliminar la partida: contiene enlaces de archivos o carpetas.')
            self.runtime.mkdir(parents=True, exist_ok=True)
            (self.runtime / PRINCIPAL_DELETED).touch()
            for entry in entries:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink(missing_ok=True)

    def delete(self, ident):
        """Delete only an inactive run while excluding other tracker windows."""
        if ident == 'principal':
            self._delete_principal()
            return
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
