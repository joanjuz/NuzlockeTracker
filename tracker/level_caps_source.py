"""Where the level caps of one run and game came from, kept apart from the caps themselves.

The stage list (``level_caps`` version 1 inside the progress file) is never changed by this
module: it only records, in its own small file, that a list proposed by Definitive Randomizer
was accepted or set aside. Removing the imported game data does not remove this record nor
the accepted stages.
"""
from __future__ import annotations

import copy
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JSONDict = dict[str, Any]

FORMAT = 'progressive-tracker-level-caps-source'
VERSION = 1
MAX_BYTES = 16_384
_SHA256 = re.compile(r'[0-9A-F]{64}\Z')
_REVISION = re.compile(r'[0-9a-f]{16}\Z')


def _sha(value: Any) -> str:
    if not isinstance(value, str) or _SHA256.match(value) is None:
        raise ValueError('Huella inválida.')
    return value


def _stamp(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 40:
        raise ValueError('Fecha inválida.')
    return value


def _accepted(value: Any) -> JSONDict | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'source', 'blockVersion', 'producer', 'game', 'dataFingerprint',
                                                     'capsFingerprint', 'tableSha256', 'checkpoints', 'finalStage',
                                                     'listRevision', 'acceptedAt'}:
        raise ValueError('Registro de aceptación inválido.')
    producer = value['producer']
    if (value['source'] != 'definitive-game-data' or value['blockVersion'] != 1 or not isinstance(producer, dict)
            or set(producer) != {'id', 'version'} or not all(isinstance(v, str) and len(v) <= 200 for v in producer.values())
            or not isinstance(value['game'], str) or len(value['game']) > 40
            or type(value['checkpoints']) is not int or not 1 <= value['checkpoints'] <= 64
            or type(value['finalStage']) is not bool
            or not isinstance(value['listRevision'], str) or _REVISION.match(value['listRevision']) is None):
        raise ValueError('Registro de aceptación inválido.')
    return {**value, 'producer': dict(producer), 'dataFingerprint': _sha(value['dataFingerprint'].upper()),
            'capsFingerprint': _sha(value['capsFingerprint']), 'tableSha256': _sha(value['tableSha256']),
            'acceptedAt': _stamp(value['acceptedAt'])}


def _dismissed(value: Any) -> JSONDict | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'capsFingerprint', 'tableSha256', 'dismissedAt'}:
        raise ValueError('Registro de propuesta descartada inválido.')
    return {'capsFingerprint': _sha(value['capsFingerprint']), 'tableSha256': _sha(value['tableSha256']),
            'dismissedAt': _stamp(value['dismissedAt'])}


class LevelCapsSource:
    """One small file per run and game. A damaged file is reported and never blocks the run."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.accepted: JSONDict | None = None
        self.dismissed: JSONDict | None = None
        self.error: str | None = None
        self.read_only = False
        if not self.path.is_file():
            return
        try:
            if self.path.stat().st_size > MAX_BYTES:
                raise ValueError('Archivo demasiado grande.')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('format') != FORMAT or type(data.get('version')) is not int or data['version'] < 1:
                raise ValueError('Formato no reconocido.')
            if data['version'] > VERSION:
                # Written by a newer tracker: kept untouched and never overwritten here.
                self.read_only = True
                self.error = 'La procedencia de los límites la guardó una versión más nueva del tracker; se conserva sin cambios.'
                return
            if set(data) - {'format', 'version', 'accepted', 'dismissed'}:
                raise ValueError('Campos desconocidos.')
            self.accepted = _accepted(data.get('accepted'))
            self.dismissed = _dismissed(data.get('dismissed'))
        except (OSError, ValueError, UnicodeError, TypeError, AttributeError, RecursionError) as exc:
            self.accepted = self.dismissed = None
            self.error = 'No se pudo leer la procedencia de los límites; los límites guardados no cambian. (' + str(exc)[:120] + ')'

    def view(self, list_revision: str | None) -> JSONDict:
        """Read-only summary. ``matchesCurrent``: the saved list is still the accepted one, unedited."""
        accepted = copy.deepcopy(self.accepted)
        return {'accepted': accepted, 'dismissed': copy.deepcopy(self.dismissed), 'error': self.error,
                'matchesCurrent': bool(accepted) and accepted['listRevision'] == list_revision}

    def check_writable(self) -> None:
        if self.read_only:
            raise ValueError('La procedencia de los límites la guardó una versión más nueva del tracker; no se modifica aquí.')

    def record_accept(self, record: JSONDict) -> None:
        """Remember the accepted proposal; raises OSError when it cannot be written (nothing is lost in memory)."""
        self.check_writable()
        accepted = _accepted({**record, 'acceptedAt': datetime.now(timezone.utc).isoformat()})
        previous = (self.accepted, self.dismissed)
        self.accepted, self.dismissed = accepted, None
        try:
            self._save()
        except OSError:
            self.accepted, self.dismissed = previous
            raise

    def record_dismiss(self, caps_fingerprint: str | None, table_sha256: str | None) -> bool:
        """Set a proposal aside (or, with ``None``, bring it back). Returns whether anything changed."""
        self.check_writable()
        dismissed = None if table_sha256 is None else _dismissed(
            {'capsFingerprint': caps_fingerprint, 'tableSha256': table_sha256,
             'dismissedAt': datetime.now(timezone.utc).isoformat()})
        same = (dismissed is None and self.dismissed is None) or (
            dismissed is not None and self.dismissed is not None
            and all(dismissed[k] == self.dismissed[k] for k in ('capsFingerprint', 'tableSha256')))
        if same:
            return False
        previous = self.dismissed
        self.dismissed = dismissed
        try:
            self._save()
        except OSError:
            self.dismissed = previous
            raise
        return True

    def _save(self) -> None:
        """Atomic and durable: temporary file, fsync and replace. An empty record removes the file."""
        if self.accepted is None and self.dismissed is None:
            self.path.unlink(missing_ok=True)
            self.error = None
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.' + secrets.token_hex(8) + '.tmp')
        try:
            with open(temporary, 'w', encoding='utf-8') as handle:
                handle.write(json.dumps({'format': FORMAT, 'version': VERSION, 'accepted': self.accepted,
                                         'dismissed': self.dismissed}, ensure_ascii=False))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.error = None
