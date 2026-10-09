"""Emulator-independent memory interface and experimental Lime3DS GDB adapter."""
import socket
from typing import Protocol

class MemoryReader(Protocol):
    def read(self, address: int, length: int) -> bytes: ...
    def close(self) -> None: ...

class LimeGDB:
    def __init__(self, port=24689, timeout=3):
        self.socket = socket.create_connection(('127.0.0.1', port), timeout)

    def _byte(self):
        b = self.socket.recv(1)
        if not b:
            raise ConnectionError('El emulador cerró la conexión.')
        return b

    def send(self, payload):
        raw = payload.encode('ascii')
        self.socket.sendall(b'$' + raw + b'#' + f'{sum(raw) & 255:02x}'.encode())

    def packet(self):
        # Skip ACKs and unrelated framing. Bounded by socket timeout.
        while self._byte() != b'$':
            pass
        data = bytearray()
        while True:
            b = self._byte()
            if b == b'#':
                break
            data.extend(b)
            if len(data) > 32768:
                raise ValueError('Respuesta GDB demasiado grande.')
        checksum = self._byte() + self._byte()
        if int(checksum, 16) != sum(data) & 255:
            self.socket.sendall(b'-')
            raise ValueError('Checksum GDB incorrecto; reconecta para continuar.')
        self.socket.sendall(b'+')
        return data.decode('ascii')

    def query(self, payload):
        self.send(payload)
        # Ignore asynchronous stop notifications and console output.
        for _ in range(32):
            reply = self.packet()
            if reply.startswith(('T', 'S', 'O')) and reply != 'OK':
                continue
            return reply
        raise ValueError('Demasiadas notificaciones GDB.')

    def identify(self):
        return self.query('qSupported')

    def resume(self):
        # Continue has no immediate response in this stub.
        self.send('c')

    def read(self, address, length):
        if not 0 <= address <= 0xffffffff or not 1 <= length <= 65536:
            raise ValueError('Dirección o tamaño inválido (máximo 65536 bytes).')
        if address + length > 0x100000000:
            raise ValueError('Lectura fuera del espacio de direcciones de 32 bits.')
        result = bytearray()
        while len(result) < length:
            count = min(256, length - len(result))
            reply = self.query(f'm{address + len(result):x},{count:x}')
            if reply.startswith('E'):
                raise ValueError(f'El emulador rechazó la lectura: {reply}')
            chunk = bytes.fromhex(reply)
            if len(chunk) != count:
                raise ValueError('Respuesta de memoria incompleta.')
            result.extend(chunk)
        return bytes(result)

    def close(self):
        # Do not send kill, detach, breakpoints, or memory writes.
        self.socket.close()
