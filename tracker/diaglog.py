"""Registro de diagnóstico local: archivo rotativo + memoria, sin secretos.

Sirve para entender fallos que el usuario solo puede describir («el sprite no se
puso en gris», «se desconecta solo»). Nunca registra tokens, invitaciones,
claves ni datos de la partida completos: cada línea pasa por `redact()`.
"""
from __future__ import annotations

import collections
import logging
import logging.handlers
import re
import threading
from pathlib import Path

ROOT_LOGGER = 'tracker'
MAX_BYTES = 512_000
BACKUPS = 3
RING_SIZE = 400

# Hex de 32+ caracteres (tokens Worker, hashes) y base64url de 40+ (sesión
# directa, invitaciones). Las rutas de Windows no coinciden: llevan \ o /.
_SECRET = re.compile(r'\b[a-fA-F0-9]{32,}\b|[A-Za-z0-9_-]{40,}')
_BEARER = re.compile(r'(?i)(bearer|token|key|clave|password|invite[_ ]?code)(["\']?\s*[:=]\s*["\']?)([^\s"\',}]+)')


def redact(text: str) -> str:
    # The field name goes too: a diagnostic should not even hint at credentials.
    text = _BEARER.sub('[oculto]', text)
    return _SECRET.sub('[oculto]', text)


class _RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


class _RingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: collections.deque[str] = collections.deque(maxlen=RING_SIZE)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.lines.append(self.format(record))
        except Exception:  # noqa: BLE001 - logging must never break the app
            self.handleError(record)


_lock = threading.Lock()
_ring = _RingHandler()
_FORMAT = _RedactingFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
_ring.setFormatter(_FORMAT)
_root = logging.getLogger(ROOT_LOGGER)
_root.setLevel(logging.INFO)
_root.addHandler(_ring)
_root.propagate = False
_file_path: Path | None = None


def setup(directory, name: str = 'tracker') -> Path | None:
    """Attach the rotating file once per process; returns its path or None."""
    global _file_path
    safe = re.sub(r'[^a-z0-9_-]', '-', str(name).lower())[:40] or 'tracker'
    path = Path(directory) / f'{safe}.log'
    with _lock:
        if _file_path == path:
            return path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding='utf-8', delay=True)
        except OSError:
            return None  # Read-only folder: keep the in-memory log only.
        handler.setFormatter(_FORMAT)
        for old in [h for h in _root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]:
            _root.removeHandler(old)
            old.close()
        _root.addHandler(handler)
        _file_path = path
        return path


def get(name: str) -> logging.Logger:
    return logging.getLogger(f'{ROOT_LOGGER}.{name}')


def recent(limit: int = 200) -> list[str]:
    """Last log lines of this session (already redacted)."""
    return list(_ring.lines)[-max(0, int(limit)):]


def close() -> None:
    """Flush and release the log file (Windows keeps open files locked)."""
    global _file_path
    with _lock:
        for handler in [h for h in _root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]:
            _root.removeHandler(handler)
            handler.close()
        _file_path = None
