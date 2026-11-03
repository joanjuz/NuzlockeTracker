"""Replay anonymised RAM fixtures (tests/fixtures/ram/*.json) through the
real decoders: decode_party, battle HP merge (Gen6/Gen7) and PC box probes.

Fixtures are produced by tools/capture_ram_fixture.py. The replay reader here
is independent from the tool: it only serves the stored byte segments and
fails any read outside them, exactly like an unmapped region.
"""
import base64
import hashlib
import importlib.util
import json
import struct
import unittest
import zlib
from dataclasses import replace
from pathlib import Path

from tracker.battle import apply_battle_hp
from tracker.battle_gen6 import apply_gen6_battle_hp
from tracker.boxes import BOX_SIZE, STORED_SIZE
from tracker.gen6_pc import Gen6BoxProbe
from tracker.gen7_pc import Gen7BoxProbe
from tracker.pokemon import PERMUTATIONS, crypt, decode_party, decode_slot
from tracker.profiles import PROFILES, capture_party

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / 'tests' / 'fixtures' / 'ram'
TOOL = ROOT / 'tools' / 'capture_ram_fixture.py'
SYNTHETIC = 'ultra-moon-sintetico-combate.json'
GENERIC_NICKNAME = 'Pokemon'
GENERIC_OT = 'Entrenador'


def load_tool():
    spec = importlib.util.spec_from_file_location('capture_ram_fixture', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_files():
    return sorted(FIXTURES.glob('*.json')) if FIXTURES.is_dir() else []


class FixtureReader:
    def __init__(self, fixture):
        self.segments = []
        for segment in fixture['segments']:
            self.assert_segment(segment)
            data = zlib.decompress(base64.b64decode(segment['data']))
            self.segments.append((int(segment['address'], 16), data))
        self.reads = []

    @staticmethod
    def assert_segment(segment):
        if segment['encoding'] != 'zlib+base64':
            raise AssertionError('codificación desconocida')
        data = zlib.decompress(base64.b64decode(segment['data']))
        if len(data) != segment['length'] or hashlib.sha256(data).hexdigest() != segment['sha256']:
            raise AssertionError(f"segmento {segment['kind']} {segment['address']} no coincide con su sha256")

    def read(self, address, length):
        self.reads.append((address, length))
        for start, data in self.segments:
            if start <= address and address + length <= start + len(data):
                return data[address - start:address - start + length]
        raise ValueError('fuera del fixture')


def stored_blocks(fixture):
    """Every non-empty encrypted PK6/PK7 block stored in a fixture."""
    for segment in fixture['segments']:
        data = zlib.decompress(base64.b64decode(segment['data']))
        if segment['kind'] == 'party':
            offsets = [i * 484 + 128 for i in range(6)]
        elif segment['kind'] == 'battle_roster':
            offsets = [i * 484 for i in range(6)]
        elif segment['kind'] == 'box':
            offsets = [i * STORED_SIZE for i in range(30)]
        else:
            continue
        for offset in offsets:
            block = data[offset:offset + STORED_SIZE]
            if any(block):
                yield block


def decrypted(block):
    seed = struct.unpack_from('<I', block)[0]
    order = PERMUTATIONS[((seed >> 13) & 31) % 24]
    shuffled = crypt(block[8:], seed)
    return block[:8] + b''.join(shuffled[order.index(k) * 56:(order.index(k) + 1) * 56] for k in range(4))


def text(data, offset):
    return data[offset:offset + 0x1A].decode('utf-16-le').split('\0')[0]


class RamFixtureReplayTests(unittest.TestCase):
    def test_every_fixture_replays_through_real_decoders(self):
        files = fixture_files()
        if not files:
            self.skipTest('No hay fixtures en tests/fixtures/ram. Captura uno con: '
                          'python tools/capture_ram_fixture.py --label equipo-ruta-1')
        for path in files:
            with self.subTest(fixture=path.name):
                self.replay(json.loads(path.read_text(encoding='utf-8')))

    def replay(self, fixture):
        self.assertEqual(fixture['schema_version'], 1)
        game = fixture['game']
        profile = replace(PROFILES[game], party_address=int(fixture['addresses']['party'], 16))
        self.assertEqual(profile.generation, fixture['generation'])
        expected = fixture['expected']
        reader = FixtureReader(fixture)
        max_species = 721 if profile.generation == 6 else 807

        party = decode_party(capture_party(reader, profile), max_species=max_species)
        self.assertEqual(len(party), 6)
        for mon, want in zip(party, expected['party']):
            if want is None:
                self.assertIsNone(mon)
                continue
            self.assertTrue(mon['checksum_valid'])
            self.assertEqual({k: mon[k] for k in want}, want)

        if profile.generation == 6:
            merged, in_battle = apply_gen6_battle_hp(reader, party, game, profile.party_address)
        else:
            merged, in_battle = apply_battle_hp(reader, party, game)
        self.assertEqual(in_battle, expected['battle_hp'])
        if in_battle:
            self.assertEqual([p['hp'] if p else None for p in merged], expected['battle_party_hp'])
        else:
            self.assertEqual(merged, party)

        boxes = expected['boxes']
        if boxes is None:
            self.assertIsNone(fixture['addresses']['box'])
            return
        base = int(boxes['box_address'], 16)
        self.assertEqual(fixture['addresses']['box'], boxes['box_address'])
        probe = Gen6BoxProbe(base) if profile.generation == 6 else Gen7BoxProbe((base,))
        for number in range(1, boxes['count'] + 1):
            probe.read(reader, number)
        chosen, decoded = probe.finish()
        self.assertEqual(chosen, base)
        occupied = [[int(box), p['slot'], p['species_id']]
                    for box in sorted(decoded, key=int) for p in decoded[box] if p is not None]
        self.assertEqual(occupied, boxes['occupied'])
        self.assertTrue(all(p['checksum_valid'] for box in decoded.values() for p in box if p))

    def test_fixtures_are_anonymised_and_bounded(self):
        files = fixture_files()
        if not files:
            self.skipTest('No hay fixtures en tests/fixtures/ram.')
        for path in files:
            with self.subTest(fixture=path.name):
                fixture = json.loads(path.read_text(encoding='utf-8'))
                stored = sum(s['length'] for s in fixture['segments'])
                # 32 boxes + party + battle data is far below any RAM dump.
                self.assertLess(stored, 32 * BOX_SIZE + 3 * 4096 + 6 * 12)
                self.assertEqual({s['kind'] for s in fixture['segments']} - {
                    'party', 'battle', 'battle_roster', 'battle_hp', 'box'}, set())
                for block in stored_blocks(fixture):
                    data = decrypted(block)
                    self.assertTrue(text(data, 0x40).startswith(GENERIC_NICKNAME))
                    self.assertEqual(text(data, 0xB0), GENERIC_OT)
                    self.assertIn(text(data, 0x78), ('', 'Cuidador'))
                    tid, sid = struct.unpack_from('<HH', data, 0x0C)
                    self.assertGreaterEqual(tid, 10000)
                    self.assertEqual(sid - tid, 10000)
                    self.assertEqual(bytes(data[0x94:0x9E]) + bytes(data[0xE0:0xE2]), bytes(12))


class SyntheticFixtureTests(unittest.TestCase):
    """The committed synthetic fixture is reproducible and ties to battle_moon.json."""

    def setUp(self):
        path = FIXTURES / SYNTHETIC
        if not path.is_file():
            self.skipTest('Falta el fixture sintético; regenéralo con '
                          'python tools/capture_ram_fixture.py --synthetic-battle-moon')
        self.fixture = json.loads(path.read_text(encoding='utf-8'))

    def test_battle_hp_matches_visible_hp_from_real_capture(self):
        samples = json.loads((ROOT / 'tests' / 'fixtures' / 'battle_moon.json').read_text())
        visible = next(s['visible_hp'] for s in samples if s['stage'] == 'battle_2')
        self.assertTrue(self.fixture['expected']['battle_hp'])
        self.assertEqual(self.fixture['expected']['battle_party_hp'][0], visible)

    def test_shiny_survives_anonymisation(self):
        self.assertEqual([p['shiny'] for p in self.fixture['expected']['party']],
                         [False, False, False, False, True, False])

    def test_regeneration_is_deterministic(self):
        tool = load_tool()
        self.assertEqual(tool.build_synthetic_battle_moon(), self.fixture)


class CaptureToolTests(unittest.TestCase):
    """capture() works on any read-only reader; Lime3DS only supplies one."""

    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()

    def test_anonymiser_rewrites_identity_and_keeps_decoded_fields(self):
        tool = self.tool
        block = bytearray(STORED_SIZE)
        seed = 0x3A5F1234
        struct.pack_into('<I', block, 0, seed)
        struct.pack_into('<H', block, 8, 448)
        struct.pack_into('<HH', block, 0x0C, 4242, 777)
        struct.pack_into('<I', block, 0x18, ((4242 ^ 777) << 16) | 9)
        block[0x1D] = 1 << 1
        tool._write_text(block, tool.NICKNAME, 'Mi Lucario')
        tool._write_text(block, tool.OT_NAME, 'Joan')
        block[0xD4:0xD7] = bytes((18, 3, 9))
        block[0xE0] = 0x31
        struct.pack_into('<H', block, 6, sum(struct.unpack('<112H', block[8:])) & 0xFFFF)
        order = PERMUTATIONS[((seed >> 13) & 31) % 24]
        encrypted = bytes(block[:8]) + crypt(b''.join(block[8 + k * 56:8 + (k + 1) * 56] for k in order), seed)
        before = decode_slot(bytes(128) + encrypted, 0)

        anonymiser = tool.Anonymiser()
        after_block = anonymiser.stored_block(encrypted)
        after = decode_slot(bytes(128) + after_block, 0)
        for field in ('species_id', 'encryption_constant', 'gender', 'shiny', 'form', 'moves'):
            self.assertEqual(after[field], before[field], field)
        self.assertTrue(after['shiny'])
        self.assertEqual(after['nickname'], 'Pokemon01')
        self.assertEqual(after['ot_id'], 10000 | (20000 << 16))
        self.assertEqual(after['met_date'], '2016-01-01')
        self.assertNotIn('Joan'.encode('utf-16-le'), decrypted(after_block))
        # Same Pokémon seen again (battle roster / box copy): same output.
        self.assertEqual(anonymiser.stored_block(encrypted), after_block)

    def test_anonymiser_rejects_bad_checksum(self):
        block = bytearray(STORED_SIZE)
        block[0] = 1
        block[100] = 5
        with self.assertRaises(ValueError):
            self.tool.Anonymiser().stored_block(bytes(block))

    def test_gen6_capture_with_battle_and_pc_round_trips(self):
        from tests.test_service_polling import RecordingGen6Memory
        for game in ('Pokémon X 1.0', 'Omega Ruby 1.0'):
            with self.subTest(game=game):
                profile = PROFILES[game]
                memory = RecordingGen6Memory(profile, battle=True)
                fixture = self.tool.capture(memory, game, profile.party_address, 'prueba', source='test')
                kinds = [s['kind'] for s in fixture['segments']]
                self.assertEqual(kinds.count('box'), 31)
                self.assertIn('battle_roster', kinds)
                self.assertEqual(kinds.count('battle_hp'), 1)
                self.assertEqual(fixture['expected']['battle_party_hp'], [11, None, None, None, None, None])
                self.assertEqual(fixture['expected']['boxes']['occupied'], [[1, 1, 25]])
                RamFixtureReplayTests().replay(fixture)
                party = next(s for s in fixture['segments'] if s['kind'] == 'party')
                raw = zlib.decompress(base64.b64decode(party['data']))
                # Wrapper header (pointers) is outside the decoded ranges.
                self.assertEqual(raw[:128], bytes(128))

    def test_capture_without_boxes_or_battle(self):
        from tests.test_service_polling import RecordingGen7Memory
        fixture = self.tool.capture(RecordingGen7Memory(), 'Ultra Moon 1.0',
                                    PROFILES['Ultra Moon 1.0'].party_address, 'x',
                                    include_boxes=False, source='test')
        self.assertEqual([s['kind'] for s in fixture['segments']], ['party'])
        self.assertFalse(fixture['expected']['battle_hp'])
        self.assertIsNone(fixture['expected']['boxes'])
        RamFixtureReplayTests().replay(fixture)

    def test_capture_refuses_empty_team(self):
        class Empty:
            def read(self, address, length):
                return bytes(length)
        with self.assertRaisesRegex(ValueError, 'No hay equipo'):
            self.tool.capture(Empty(), 'Ultra Moon 1.0', PROFILES['Ultra Moon 1.0'].party_address, 'x')

    def test_reader_only_needs_read(self):
        # The tool must never call anything but read() on the emulator reader.
        from tests.test_service_polling import RecordingGen7Memory
        memory = RecordingGen7Memory()

        class Strict:
            def read(self, address, length):
                return memory.read(address, length)
        self.tool.capture(Strict(), 'Ultra Moon 1.0', PROFILES['Ultra Moon 1.0'].party_address, 'x', source='test')

    def test_fixture_names_and_overwrite_protection(self):
        import tempfile
        self.assertEqual(self.tool.fixture_filename('Pokémon X 1.0', 'a'), 'pokemon-x-a.json')
        self.assertEqual(self.tool.fixture_filename('Alpha Sapphire 1.0', 'b'), 'alpha-sapphire-b.json')
        with tempfile.TemporaryDirectory() as folder:
            data = {'game': 'Ultra Sun 1.0', 'label': 'l'}
            path = self.tool.write_fixture(data, Path(folder))
            self.assertEqual(path.name, 'ultra-sun-l.json')
            with self.assertRaises(FileExistsError):
                self.tool.write_fixture(data, Path(folder))

    def test_cli_rejects_bad_label_before_touching_emulator(self):
        with self.assertRaises(SystemExit):
            import contextlib
            import io
            with contextlib.redirect_stderr(io.StringIO()):
                self.tool.main(['--label', 'Nombre Con Espacios'])


if __name__ == '__main__':
    unittest.main()
