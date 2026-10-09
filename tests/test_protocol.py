import unittest
from tracker.connectors import LimeGDB
class Wire:
    def __init__(self, data): self.data, self.sent = bytearray(data), []
    def recv(self, n):
        result = bytes(self.data[:n]); del self.data[:n]; return result
    def sendall(self, data): self.sent.append(data)
def packet(payload):
    raw = payload.encode()
    return b'$' + raw + b'#' + f'{sum(raw) & 255:02x}'.encode()
def client(data):
    c = object.__new__(LimeGDB); c.socket = Wire(data); return c
class ProtocolTests(unittest.TestCase):
    def test_read(self):
        c = client(b'+' + packet('0102'))
        self.assertEqual(c.read(0x1000, 2), b'\x01\x02')
        self.assertEqual(c.socket.sent, [packet('m1000,2'), b'+'])
    def test_chunking(self):
        c = client(packet('00' * 256) + packet('ab' * 4))
        self.assertEqual(c.read(0x1000, 260), bytes(256) + b'\xab' * 4)
        self.assertIn(packet('m1100,4'), c.socket.sent)
    def test_bad_checksum(self):
        c = client(b'$0102#00')
        with self.assertRaises(ValueError): c.read(0x1000, 2)
        self.assertEqual(c.socket.sent[-1], b'-')
    def test_invalid_memory(self):
        with self.assertRaisesRegex(ValueError, 'rechazó'): client(packet('E00')).read(0x1000, 2)
    def test_stop_notification(self):
        self.assertEqual(client(packet('T05thread:1;') + packet('0102')).read(0x1000, 2), b'\x01\x02')
    def test_truncated_response(self):
        with self.assertRaisesRegex(ValueError, 'incompleta'): client(packet('01')).read(0x1000, 2)
    def test_closed_connection(self):
        with self.assertRaises(ConnectionError): client(b'').identify()
    def test_limits(self):
        c = client(b'')
        for address, length in [(-1, 1), (0, 0), (0, 65537), (0xffffffff, 2)]:
            with self.assertRaises(ValueError): c.read(address, length)
        self.assertEqual(c.socket.sent, [])
    def test_resume(self):
        c = client(b''); c.resume(); self.assertEqual(c.socket.sent, [packet('c')])
if __name__ == '__main__': unittest.main()
