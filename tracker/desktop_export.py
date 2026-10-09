"""Save portable backups through the native WebView2 file-picker.

The dialog decides the destination. Never expose an arbitrary file path via
HTTP or allow the browser to write a user-supplied path. Automatic runtime
saves remain independent of these optional user exports.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path


def export_payload(service, kind):
    if kind == 'session':
        return service.session_export()
    if kind == 'diagnostic':
        return service.diagnostic_export()
    raise ValueError('Tipo de exportación inválido')


def write_export(destination, payload):
    """Write UTF-8 JSON atomically in the user-selected directory."""
    path = Path(destination)
    if path.suffix.lower() != '.json':
        path = path.with_name(path.name + '.json')
    if not path.parent.is_dir():
        raise FileNotFoundError('La carpeta seleccionada ya no existe.')
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', prefix='.tracker-',
                                         suffix='.tmp', dir=path.parent,
                                         delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return path


class DesktopExportApi:
    """Methods exposed only to the local pywebview JS bridge."""
    def __init__(self, service, window=None):
        self.service = service
        self.window = window
        self.lock = threading.Lock()

    def save_export(self, kind):
        if kind not in ('session', 'diagnostic'):
            return {'error': 'Exportación no permitida'}
        if not self.lock.acquire(blocking=False):
            return {'error': 'Ya existe un diálogo de guardado abierto'}
        try:
            import webview
            if self.window is None:
                return {'error': 'La ventana todavía no está lista'}
            prefix = 'sesion' if kind == 'session' else 'diagnostico'
            suggested = f'{prefix}_pokemon_{datetime.now():%Y%m%d_%H%M%S}.json'
            selected = self.window.create_file_dialog(
                webview.FileDialog.SAVE, save_filename=suggested,
                file_types=('Archivo JSON (*.json)',))
            if not selected:
                return {'cancelled': True}
            # pywebview returns one or more paths as tuple/list.
            destination = selected[0] if isinstance(selected, (tuple, list)) else selected
            if not isinstance(destination, str) or not destination.strip():
                return {'error': 'No se seleccionó un archivo válido'}
            payload = export_payload(self.service, kind)
            output = write_export(destination, payload)
            return {'saved': True, 'name': output.name}
        except (OSError, ValueError, TypeError) as exc:
            return {'error': str(exc)}
        finally:
            self.lock.release()
