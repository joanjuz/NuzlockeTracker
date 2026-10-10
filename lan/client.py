"""Publish only a sanitized summary from a local loopback Pokémon Tracker."""
from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
import ipaddress
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from .protocol import SLOTS, public_state, safe_string


def validate_local(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1') or not parsed.port or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('La URL del tracker debe ser http://127.0.0.1:PUERTO/ (solo esta computadora)')
    return 'http://127.0.0.1:' + str(parsed.port)


def validate_host(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or not parsed.hostname or not parsed.port or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('La URL de sala debe ser http://IP_LOCAL:PUERTO/ sin claves en la URL')
    # Require a literal RFC1918 address or loopback to prevent accidental Internet exposure.
    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        raise ValueError('Introduce la IP local del anfitrion, no un dominio') from exc
    if not (ip.is_loopback or ip.version == 4 and any(ip in net for net in (
        ipaddress.ip_network('10.0.0.0/8'), ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16')))):
        raise ValueError('La sala debe estar en una IP privada (LAN), no en Internet')
    return url.rstrip('/')


def publish_once(local, host, slot, token, name=None):
    with urlopen(local + '/api/state', timeout=4) as response:
        if response.status != 200:
            raise OSError('El tracker no responde correctamente')
        raw = response.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        raise ValueError('Estado local demasiado grande')
    data = public_state(json.loads(raw))
    if data['game'] != SLOTS[slot][1]:
        raise ValueError('Puesto ' + slot + ' requiere ' + SLOTS[slot][1] + '; juego actual: ' + data['game'])
    if name:
        data['display_name'] = safe_string(name, 24)
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    req = Request(host + '/api/player', body, {'Authorization': 'Bearer ' + token,
                                               'X-Player-Slot': slot,
                                               'Content-Type': 'application/json'}, method='POST')
    with urlopen(req, timeout=4) as response:
        if response.status != 200:
            raise OSError('El servidor rechazo la publicacion')
    return data


def main():
    parser = argparse.ArgumentParser(description='Comparte tu equipo con una sala LAN sin compartir memoria')
    parser.add_argument('--tracker', required=True, help='URL local que aparece en la consola de Iniciar.bat')
    parser.add_argument('--host', required=True, help='http://IP_DEL_ANFITRION:8765')
    parser.add_argument('--slot', required=True, choices=SLOTS.keys())
    parser.add_argument('--token', required=True, help='Clave privada de tu puesto')
    parser.add_argument('--name', default='', help='Nombre visible en la sala (opcional)')
    parser.add_argument('--interval', type=float, default=2.0)
    args = parser.parse_args()
    local, host = validate_local(args.tracker), validate_host(args.host)
    if not 1.0 <= args.interval <= 30.0:
        parser.error('Intervalo invalido (1-30 segundos)')
    print('Compartiendo solo resumen de equipo, sin cajas ni datos de RAM. Ctrl+C para salir.')
    last = None
    try:
        while True:
            try:
                data = publish_once(local, host, args.slot, args.token, args.name)
                message = 'En linea' if data['online'] else 'Tracker desconectado'
                if message != last:
                    print(message + ' | ' + data['game'] + ' | ' + args.slot)
                    last = message
            except (OSError, ValueError, HTTPError, URLError) as exc:
                print('Aviso: ' + str(exc))
                last = None
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('\nCliente detenido.')


if __name__ == '__main__':
    main()
