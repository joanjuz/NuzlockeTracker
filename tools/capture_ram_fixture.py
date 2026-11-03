"""Captura un fixture de RAM anonimizado para las pruebas de regresión.

Uso (Windows, con Lime3DS/Azahar abierto y una partida cargada que tenga al
menos un Pokémon en el equipo):

    python tools/capture_ram_fixture.py --label equipo-ruta-1

Se guarda en ``tests/fixtures/ram/<juego>-<label>.json`` y después basta con
``python -m unittest tests.test_ram_fixtures -v`` para reproducirlo.

Opciones:
    --game "Ultra Moon 1.0"   Juego, si el título de la ventana no lo indica.
                              Valores: Ultra Moon 1.0, Ultra Sun 1.0,
                              Pokémon X 1.0, Pokémon Y 1.0, Omega Ruby 1.0,
                              Alpha Sapphire 1.0.
    --pid 1234                Proceso concreto, si hay varios emuladores.
    --sin-cajas               No lee el PC (solo equipo y combate).
    --output CARPETA          Carpeta de destino (por defecto tests/fixtures/ram).
    --force                   Sobrescribe un fixture con el mismo nombre.

Para incluir los PS de combate, ejecútalo durante un combate individual con el
menú de movimientos en pantalla (pausar el emulador ayuda a que las dos
lecturas coincidan). Fuera de combate se captura solo equipo y PC.

Qué hace y qué no hace:
    * Solo LEE memoria, con el mismo LimeProcessMemory que usa el tracker.
      No escribe en el proceso, la ROM ni la partida.
    * Recorre el mismo camino de decodificación que el tracker (decode_party,
      PS de combate, sondas de cajas Gen6/Gen7) y guarda únicamente los bytes
      que ese camino decodifica: los bloques PK6/PK7 del equipo, los campos de
      combate que se comparan y las cajas del PC verificado. Cualquier otro
      byte de esos rangos se guarda a cero. Nunca guarda un volcado completo.
    * Anonimiza cada Pokémon: mote, nombre del entrenador original y del
      último cuidador pasan a textos genéricos; TID/SID se sustituyen por IDs
      genéricos (el mismo par original recibe siempre el mismo par nuevo) y se
      ajusta el PID para conservar el estado variocolor; fechas de captura y
      huevo pasan a 2016-01-01; país, región, región de consola, idioma, sexo
      del entrenador, recuerdos y memorias geográficas a cero.
      Después se recalcula la suma de comprobación y se vuelve a cifrar.
    * Las expectativas (especies, niveles, PS, cajas) se calculan
      reproduciendo los bytes ya anonimizados y se contrastan con la lectura
      en vivo antes de guardar. Si no coinciden, no se guarda nada.

Revisa el JSON antes de subirlo al repositorio.

Mantenimiento: ``--synthetic-battle-moon`` regenera el fixture sintético
construido a partir de tests/fixtures/battle_moon.json (no necesita emulador).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import struct
import sys
import zlib
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tracker.battle import BATTLE_START, LENGTH as GEN7_BATTLE_LENGTH, STRIDE as GEN7_BATTLE_STRIDE, apply_battle_hp  # noqa: E402
from tracker.battle_gen6 import STRIDE as GEN6_HP_STRIDE, apply_gen6_battle_hp, candidate_pairs  # noqa: E402
from tracker.boxes import BOX_SIZE, SLOTS, STORED_SIZE  # noqa: E402
from tracker.gen6_pc import Gen6BoxProbe  # noqa: E402
from tracker.gen7_pc import Gen7BoxProbe  # noqa: E402
from tracker.pokemon import PERMUTATIONS, crypt, decode_party  # noqa: E402
from tracker.profiles import PROFILES, capture_party  # noqa: E402

SCHEMA_VERSION = 1
DEFAULT_OUTPUT = ROOT / 'tests' / 'fixtures' / 'ram'
PARTY_SLOT_STRIDE = 484
PARTY_STORED_OFFSET = 128      # decode_slot(): snapshot[start+128:start+360]
PARTY_TAIL_OFFSET = 472        # decode_slot(): snapshot[start+472:start+494]
PARTY_TAIL_SIZE = 22
GEN6_ROSTER_LENGTH = 484 * 5 + 366   # apply_gen6_battle_hp() read length
GEN6_ROSTER_TAIL = 344               # tail offset inside a battle roster slot
GEN6_HP_BACK = 266                   # hp block starts 266 bytes before the reference
GEN6_HP_LENGTH = 12

# Fields of the decrypted PK6/PK7 stored block (identical layout, PKHeX).
NICKNAME = (0x40, 0x1A)
HANDLER_NAME = (0x78, 0x1A)
GEO_MEMORIES = (0x94, 10)
OT_NAME = (0xB0, 0x1A)
EGG_DATE = 0xD1
MET_DATE = 0xD4
COUNTRY_REGION = (0xE0, 2)
CONSOLE_REGION_LANGUAGE = (0xE2, 2)
HT_MEMORIES = (0xA4, 6)    # HT intensity, memory, feeling, text variable
OT_MEMORIES = (0xCC, 5)    # OT intensity, memory, text variable, feeling
MET_LEVEL_OT_GENDER = 0xDD  # bits 0-6 met level (decoded), bit 7 OT gender
GENERIC_OT = 'Entrenador'
GENERIC_HANDLER = 'Cuidador'
GENERIC_DATE = (16, 1, 1)      # 2016-01-01


class Reader(Protocol):
    def read(self, address: int, length: int) -> bytes: ...


Range = tuple[int, int]


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------
class Anonymiser:
    """Rewrites identifying PK6/PK7 fields consistently across one capture."""

    def __init__(self) -> None:
        self.trainers: dict[tuple[int, int], tuple[int, int]] = {}
        self.nicknames: dict[int, str] = {}

    def _trainer(self, tid: int, sid: int) -> tuple[int, int]:
        if (tid, sid) not in self.trainers:
            n = len(self.trainers)
            self.trainers[(tid, sid)] = (10000 + n, 20000 + n)
        return self.trainers[(tid, sid)]

    def _nickname(self, encryption_constant: int) -> str:
        if encryption_constant not in self.nicknames:
            self.nicknames[encryption_constant] = f'Pokemon{len(self.nicknames) + 1:02d}'
        return self.nicknames[encryption_constant]

    def stored_block(self, block: bytes) -> bytes:
        """Return an anonymised copy of one encrypted 232-byte block.

        Empty (all-zero) blocks are returned unchanged. A block with an
        invalid checksum raises ValueError: it was not decoded by the tracker.
        """
        if len(block) != STORED_SIZE:
            raise ValueError('Bloque PK6/PK7 incompleto')
        if not any(block):
            return block
        seed, sanity, checksum = struct.unpack_from('<IHH', block)
        order = PERMUTATIONS[((seed >> 13) & 31) % 24]
        shuffled = crypt(block[8:], seed)
        data = bytearray(block[:8] + b''.join(
            shuffled[order.index(k) * 56:(order.index(k) + 1) * 56] for k in range(4)))
        if sanity or sum(struct.unpack('<112H', data[8:])) & 0xFFFF != checksum:
            raise ValueError('Bloque PK6/PK7 con checksum inválido; no se anonimiza')
        tid, sid = struct.unpack_from('<HH', data, 0x0C)
        new_tid, new_sid = self._trainer(tid, sid)
        struct.pack_into('<HH', data, 0x0C, new_tid, new_sid)
        # Preserve the shiny XOR exactly: (TID^SID) changes, so does PID low word.
        pid = struct.unpack_from('<I', data, 0x18)[0]
        pid ^= (tid ^ sid) ^ (new_tid ^ new_sid)
        struct.pack_into('<I', data, 0x18, pid)
        _write_text(data, NICKNAME, self._nickname(seed))
        if any(data[HANDLER_NAME[0]:HANDLER_NAME[0] + HANDLER_NAME[1]]):
            _write_text(data, HANDLER_NAME, GENERIC_HANDLER)
        _write_text(data, OT_NAME, GENERIC_OT)
        data[GEO_MEMORIES[0]:GEO_MEMORIES[0] + GEO_MEMORIES[1]] = bytes(GEO_MEMORIES[1])
        data[COUNTRY_REGION[0]:COUNTRY_REGION[0] + COUNTRY_REGION[1]] = bytes(COUNTRY_REGION[1])
        # Not decoded by the tracker, but they describe the player: zero them.
        for offset, size in (CONSOLE_REGION_LANGUAGE, HT_MEMORIES, OT_MEMORIES):
            data[offset:offset + size] = bytes(size)
        data[MET_LEVEL_OT_GENDER] &= 0x7F  # keep the met level, drop the OT gender
        for offset in (EGG_DATE, MET_DATE):
            if any(data[offset:offset + 3]):
                data[offset:offset + 3] = bytes(GENERIC_DATE)
        struct.pack_into('<H', data, 6, sum(struct.unpack('<112H', data[8:])) & 0xFFFF)
        reshuffled = b''.join(data[8 + k * 56:8 + (k + 1) * 56] for k in order)
        return bytes(data[:8]) + crypt(reshuffled, seed)


def _write_text(data: bytearray, field: Range, text: str) -> None:
    offset, size = field
    encoded = text.encode('utf-16-le')[:size - 2]
    data[offset:offset + size] = encoded + bytes(size - len(encoded))


# ---------------------------------------------------------------------------
# Masks: keep only the bytes each decoder reads, zero everything else.
# ---------------------------------------------------------------------------
def keep_ranges(raw: bytes, ranges: Iterable[Range]) -> bytearray:
    result = bytearray(len(raw))
    for start, size in ranges:
        result[start:start + size] = raw[start:start + size]
    return result


def party_ranges() -> list[Range]:
    return [r for i in range(6) for r in (
        (i * PARTY_SLOT_STRIDE + PARTY_STORED_OFFSET, STORED_SIZE),
        (i * PARTY_SLOT_STRIDE + PARTY_TAIL_OFFSET, PARTY_TAIL_SIZE))]


def gen6_roster_ranges() -> list[Range]:
    return [r for i in range(6) for r in (
        (i * PARTY_SLOT_STRIDE, STORED_SIZE),
        (i * PARTY_SLOT_STRIDE + GEN6_ROSTER_TAIL, PARTY_TAIL_SIZE))]


GEN7_BATTLE_RANGES: list[Range] = [(i * GEN7_BATTLE_STRIDE, 13) for i in range(6)]
GEN6_HP_RANGES: list[Range] = [(0, 4), (8, 1), (10, 1)]


def anonymise_blocks(raw: bytearray, offsets: Iterable[int], anonymiser: Anonymiser) -> bytes:
    for offset in offsets:
        raw[offset:offset + STORED_SIZE] = anonymiser.stored_block(bytes(raw[offset:offset + STORED_SIZE]))
    return bytes(raw)


# ---------------------------------------------------------------------------
# Recording and replay readers
# ---------------------------------------------------------------------------
class RecordingReader:
    """Read-only proxy that remembers the first bytes returned for each read."""

    def __init__(self, reader: Reader) -> None:
        self.reader = reader
        self.first: dict[Range, bytes] = {}

    def read(self, address: int, length: int) -> bytes:
        data = self.reader.read(address, length)
        self.first.setdefault((address, length), bytes(data))
        return data


class SegmentReader:
    """Serves reads fully contained in stored segments; anything else fails."""

    def __init__(self, segments: Iterable[tuple[int, bytes]]) -> None:
        self.segments = list(segments)

    def read(self, address: int, length: int) -> bytes:
        for start, data in self.segments:
            if start <= address and address + length <= start + len(data):
                return data[address - start:address - start + length]
        raise ValueError(f'Lectura fuera del fixture: {address:#x}+{length}')


def encode_segment(kind: str, address: int, data: bytes, **extra: Any) -> dict[str, Any]:
    return {'kind': kind, 'address': hex(address), 'length': len(data), **extra,
            'encoding': 'zlib+base64', 'sha256': hashlib.sha256(data).hexdigest(),
            'data': base64.b64encode(zlib.compress(data, 9)).decode('ascii')}


def decode_segment(segment: dict[str, Any]) -> tuple[int, bytes]:
    if segment.get('encoding') != 'zlib+base64':
        raise ValueError('Codificación de segmento desconocida')
    data = zlib.decompress(base64.b64decode(segment['data']))
    if len(data) != segment['length'] or hashlib.sha256(data).hexdigest() != segment['sha256']:
        raise ValueError(f"Segmento {segment['kind']} {segment['address']} dañado (sha256)")
    return int(segment['address'], 16), data


# ---------------------------------------------------------------------------
# Decode path shared by capture (live) and replay (fixture)
# ---------------------------------------------------------------------------
def _box_probe(profile: Any, include_boxes: bool) -> tuple[Callable[[], Any], int] | None:
    if not include_boxes:
        return None
    if profile.generation == 6:
        shift = profile.party_address - PROFILES[profile.name].party_address
        return (lambda: Gen6BoxProbe(profile.box_address, shift)), 31
    from tracker.service import TrackerService
    return (lambda: Gen7BoxProbe(TrackerService.gen7_box_candidates(profile))), 32


def run_decode_path(reader: Reader, game: str, party_address: int,
                    box_addresses: tuple[int, ...] | None = None,
                    include_boxes: bool = True) -> dict[str, Any]:
    """Party -> battle HP -> PC, exactly through the tracker decoders."""
    profile = replace(PROFILES[game], party_address=party_address)
    max_species = 721 if profile.generation == 6 else 807
    party = decode_party(capture_party(reader, profile), max_species=max_species)
    if not any(party):
        raise ValueError('No hay equipo válido en memoria: carga una partida con al menos un Pokémon.')
    report: dict[str, Any] = {}
    if profile.generation == 6:
        merged, in_battle = apply_gen6_battle_hp(reader, party, game, party_address, report)
    else:
        merged, in_battle = apply_battle_hp(reader, party, game)
    result: dict[str, Any] = {'profile': profile, 'party': party, 'merged': merged,
                              'battle_hp': in_battle, 'battle_report': report,
                              'box_address': None, 'boxes': None, 'box_count': 0}
    if box_addresses is not None:
        if profile.generation == 6:
            factory, count = (lambda: _Gen6Fixed(box_addresses)), 31
        else:
            factory, count = (lambda: Gen7BoxProbe(box_addresses)), 32
    else:
        probe_info = _box_probe(profile, include_boxes)
        if probe_info is None:
            return result
        factory, count = probe_info
    probe = factory()
    for number in range(1, count + 1):
        probe.read(reader, number)
    chosen, boxes = probe.finish()
    result.update(box_address=chosen, boxes=boxes, box_count=count)
    return result


class _Gen6Fixed(Gen6BoxProbe):
    """Gen6 probe pinned to the recorded base (replay only)."""

    def __init__(self, addresses: tuple[int, ...]) -> None:
        super().__init__(addresses[0], 0)


def summarise(result: dict[str, Any]) -> dict[str, Any]:
    """Stable expectations stored next to the bytes."""
    def mon(p: dict[str, Any] | None) -> dict[str, Any] | None:
        if p is None:
            return None
        return {k: p[k] for k in ('slot', 'species_id', 'level', 'hp', 'max_hp',
                                  'checksum_valid', 'egg', 'gender', 'shiny')}
    expected: dict[str, Any] = {
        'party': [mon(p) for p in result['party']],
        'battle_hp': result['battle_hp'],
        'battle_party_hp': [p['hp'] if p else None for p in result['merged']] if result['battle_hp'] else None,
        'boxes': None,
    }
    if result['box_address'] is not None:
        boxes = result['boxes']
        expected['boxes'] = {
            'box_address': hex(result['box_address']),
            'count': result['box_count'],
            'occupied': [[int(box), p['slot'], p['species_id']]
                         for box in sorted(boxes, key=int) for p in boxes[box] if p is not None],
        }
    return expected


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
def capture(reader: Reader, game: str, party_address: int, label: str,
            include_boxes: bool = True, source: str = 'lime3ds') -> dict[str, Any]:
    """Build an anonymised fixture from any read-only reader."""
    if game not in PROFILES:
        raise ValueError(f'Juego desconocido: {game}')
    recorder = RecordingReader(reader)
    live = run_decode_path(recorder, game, party_address, include_boxes=include_boxes)
    profile = live['profile']
    anonymiser = Anonymiser()
    segments: list[dict[str, Any]] = []

    party_key = (party_address, profile.slot_stride * 5 + 494)
    party_raw = keep_ranges(recorder.first[party_key], party_ranges())
    segments.append(encode_segment('party', party_address, anonymise_blocks(
        party_raw, (i * PARTY_SLOT_STRIDE + PARTY_STORED_OFFSET for i in range(6)), anonymiser)))

    addresses: dict[str, Any] = {'party': hex(party_address), 'box': None,
                                 'battle': None, 'battle_party_shift': None}
    if live['battle_hp']:
        if profile.generation == 7:
            raw = recorder.first[(BATTLE_START, GEN7_BATTLE_LENGTH)]
            segments.append(encode_segment('battle', BATTLE_START,
                                           bytes(keep_ranges(raw, GEN7_BATTLE_RANGES))))
            addresses['battle'] = hex(BATTLE_START)
        else:
            report = live['battle_report']
            candidate = int(report['battle_candidate'], 16)
            offset = report['battle_party_shift']
            roster = keep_ranges(recorder.first[(candidate, GEN6_ROSTER_LENGTH)], gen6_roster_ranges())
            segments.append(encode_segment('battle_roster', candidate, anonymise_blocks(
                roster, (i * PARTY_SLOT_STRIDE for i in range(6)), anonymiser)))
            hp_base = next(hp + offset for base, hp in candidate_pairs(game) if base + offset == candidate)
            for i, p in enumerate(live['party']):
                if p is None:
                    continue
                address = hp_base + i * GEN6_HP_STRIDE - GEN6_HP_BACK
                raw = recorder.first[(address, GEN6_HP_LENGTH)]
                segments.append(encode_segment('battle_hp', address,
                                               bytes(keep_ranges(raw, GEN6_HP_RANGES)), slot=i + 1))
            addresses['battle'] = hex(candidate)
            addresses['battle_party_shift'] = offset
    if live['box_address'] is not None:
        base = live['box_address']
        addresses['box'] = hex(base)
        for number in range(1, live['box_count'] + 1):
            address = base + (number - 1) * BOX_SIZE
            raw = bytearray(recorder.first[(address, BOX_SIZE)])
            segments.append(encode_segment('box', address, anonymise_blocks(
                raw, (i * STORED_SIZE for i in range(SLOTS)), anonymiser), box=number))

    fixture: dict[str, Any] = {
        'schema_version': SCHEMA_VERSION,
        'game': game,
        'generation': profile.generation,
        'label': label,
        'source': source,
        'captured_on': date.today().isoformat() if source == 'lime3ds' else None,
        'addresses': addresses,
        'segments': segments,
    }
    replayed = replay(fixture)
    _check_against_live(live, replayed)
    fixture['expected'] = summarise(replayed)
    return fixture


def replay(fixture: dict[str, Any]) -> dict[str, Any]:
    """Decode a fixture's bytes through the tracker decoders."""
    reader = SegmentReader(decode_segment(s) for s in fixture['segments'])
    box = fixture['addresses'].get('box')
    return run_decode_path(reader, fixture['game'], int(fixture['addresses']['party'], 16),
                           box_addresses=(int(box, 16),) if box else None, include_boxes=False)


def _check_against_live(live: dict[str, Any], replayed: dict[str, Any]) -> None:
    """Anonymisation must not change anything the tracker relies on."""
    fields = ('species_id', 'level', 'hp', 'max_hp', 'ability_id', 'encryption_constant',
              'egg', 'gender', 'shiny', 'form', 'moves', 'origin_version')
    for key in ('party', 'merged'):
        for a, b in zip(live[key], replayed[key]):
            if (a is None) != (b is None) or (a and any(a[f] != b[f] for f in fields)):
                raise ValueError('La reproducción anonimizada no coincide con la lectura en vivo')
    if live['battle_hp'] != replayed['battle_hp'] or live['box_address'] != replayed['box_address']:
        raise ValueError('La reproducción anonimizada no coincide con la lectura en vivo (combate/PC)')
    if live['boxes'] is not None:
        def layout(boxes: dict[str, list[Any]]) -> list[Any]:
            return [(k, p['slot'], p['species_id'], p['shiny']) for k in sorted(boxes, key=int)
                    for p in boxes[k] if p]
        if layout(live['boxes']) != layout(replayed['boxes']):
            raise ValueError('La reproducción anonimizada no coincide con el PC en vivo')


def fixture_filename(game: str, label: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', game.casefold().replace('é', 'e').replace(' 1.0', '')).strip('-')
    return f'{slug}-{label}.json'


def write_fixture(fixture: dict[str, Any], folder: Path, force: bool = False) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / fixture_filename(fixture['game'], fixture['label'])
    if path.exists() and not force:
        raise FileExistsError(f'{path} ya existe; usa otro --label o --force')
    path.write_text(json.dumps(fixture, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return path


# ---------------------------------------------------------------------------
# Synthetic fixture from tests/fixtures/battle_moon.json (no emulator)
# ---------------------------------------------------------------------------
def _synthetic_slot(index: int, mon: dict[str, Any]) -> tuple[bytes, bytes]:
    """Encrypted stored block + stats tail for a battle_moon.json team member."""
    seed = 0x1000 + index * 0x2345 + (index << 13)
    data = bytearray(STORED_SIZE)
    struct.pack_into('<I', data, 0, seed)
    struct.pack_into('<H', data, 8, mon['species_id'])
    struct.pack_into('<HH', data, 0x0C, 0xBEEF, 0xCAFE)       # stand-in personal IDs
    # Slot 5 is shiny (TID^SID^PIDhi^PIDlo == 3) to prove anonymisation keeps it.
    pid = (((0xBEEF ^ 0xCAFE) << 16) | 3) if index == 4 else 0x12345678 + index
    struct.pack_into('<I', data, 0x18, pid)
    data[0x14] = mon['ability_id']
    data[0x1D] = 2 if index % 2 else 0
    _write_text(data, NICKNAME, 'Apodo' + str(index))
    _write_text(data, OT_NAME, 'Jugadora')
    _write_text(data, HANDLER_NAME, 'Amigo')
    data[MET_DATE:MET_DATE + 3] = bytes((17, 11, 17))
    data[0xE0:0xE2] = bytes((0x31, 7))
    data[0xDF] = 33
    struct.pack_into('<H', data, 6, sum(struct.unpack('<112H', data[8:])) & 0xFFFF)
    order = PERMUTATIONS[((seed >> 13) & 31) % 24]
    block = bytes(data[:8]) + crypt(b''.join(data[8 + k * 56:8 + (k + 1) * 56] for k in order), seed)
    tail = bytearray(PARTY_TAIL_SIZE)
    tail[4] = mon['level']
    struct.pack_into('<7H', tail, 8, mon['hp'], mon['max_hp'], 100, 100, 100, 100, 100)
    return block, crypt(bytes(tail), seed)


def build_synthetic_battle_moon(stage: str = 'battle_2') -> dict[str, Any]:
    """Team PK7 bytes are synthetic; the battle block is the real capture."""
    from tracker.profiles import ULTRA_MOON_10
    samples = json.loads((ROOT / 'tests' / 'fixtures' / 'battle_moon.json').read_text(encoding='utf-8'))
    sample = next(s for s in samples if s['stage'] == stage)
    party = bytearray(ULTRA_MOON_10.slot_stride * 5 + 494)
    blocks = []
    for i, mon in enumerate(sample['party']):
        block, tail = _synthetic_slot(i, mon)
        start = i * PARTY_SLOT_STRIDE
        party[start + PARTY_STORED_OFFSET:start + PARTY_STORED_OFFSET + STORED_SIZE] = block
        party[start + PARTY_TAIL_OFFSET:start + PARTY_TAIL_OFFSET + PARTY_TAIL_SIZE] = tail
        blocks.append(block)
    box1 = bytearray(BOX_SIZE)
    box1[0:STORED_SIZE] = blocks[0]
    box1[4 * STORED_SIZE:5 * STORED_SIZE] = blocks[4]
    memory = SegmentReader([
        (ULTRA_MOON_10.party_address, bytes(party)),
        (BATTLE_START, bytes.fromhex(sample['raw_hex'])[:GEN7_BATTLE_LENGTH]),
        (ULTRA_MOON_10.box_address, bytes(box1) + bytes(31 * BOX_SIZE)),
    ])
    return capture(memory, ULTRA_MOON_10.name, ULTRA_MOON_10.party_address,
                   label='sintetico-combate', source=f'synthetic: tests/fixtures/battle_moon.json {stage}')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _select_game(game: str | None, pid: int | None) -> tuple[str, int | None]:
    from tracker.process_memory import list_emulator_instances
    try:
        instances = list_emulator_instances()
    except OSError:
        instances = []
    if pid is not None:
        instances = [m for m in instances if m.get('pid') == pid]
    if len(instances) > 1:
        listed = ', '.join(f"PID {m['pid']} ({m.get('title') or m.get('name')})" for m in instances)
        raise ValueError(f'Hay varios emuladores abiertos: {listed}. Indica --pid.')
    hint = instances[0].get('game_hint') if instances else None
    if pid is None and instances:
        pid = instances[0]['pid']
    if game and hint and hint != game:
        raise ValueError(f'El emulador parece ejecutar {hint}, no {game}.')
    if not (game or hint):
        raise ValueError('No se pudo identificar el juego por el título de la ventana. Usa --game.')
    return game or hint, pid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Captura un fixture de RAM anonimizado (solo lectura).')
    parser.add_argument('--label', help='Nombre corto: minúsculas, números y guiones (p. ej. equipo-ruta-1).')
    parser.add_argument('--game', choices=sorted(PROFILES), help='Juego cargado, si no se detecta.')
    parser.add_argument('--pid', type=int, help='PID del emulador, si hay varios.')
    parser.add_argument('--sin-cajas', action='store_true', help='No leer el PC.')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='Carpeta de destino.')
    parser.add_argument('--force', action='store_true', help='Sobrescribir un fixture existente.')
    parser.add_argument('--synthetic-battle-moon', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.synthetic_battle_moon:
            fixture = build_synthetic_battle_moon()
        else:
            if not args.label or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}', args.label):
                parser.error('--label es obligatorio: minúsculas, números y guiones (máx. 40).')
            from tracker.process_memory import LimeProcessMemory
            game, pid = _select_game(args.game, args.pid)
            print(f'Juego: {game}. Localizando RAM (solo lectura)...')
            reader = LimeProcessMemory(pid, print, dynamic=True, generation=PROFILES[game].generation)
            try:
                fixture = capture(reader, game, reader.party_address, args.label,
                                  include_boxes=not args.sin_cajas)
            finally:
                reader.close()
        path = write_fixture(fixture, args.output, force=args.force or args.synthetic_battle_moon)
    except (ValueError, OSError) as exc:
        print('No se guardó el fixture:', exc, file=sys.stderr)
        return 1
    expected = fixture['expected']
    team = sum(p is not None for p in expected['party'])
    boxes = expected['boxes']
    print(f'Guardado: {path}')
    print(f"Equipo: {team} Pokémon · combate: {'sí' if expected['battle_hp'] else 'no'} · "
          f"PC: {len(boxes['occupied']) if boxes else 'no verificado'}"
          f"{' Pokémon' if boxes else ''}")
    print('Revisa el archivo antes de subirlo. Ejecuta: python -m unittest tests.test_ram_fixtures -v')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
