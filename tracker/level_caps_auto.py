"""Optional confirmed suggestions for advancing manual level-cap stages.

Kept apart from the stage list on purpose: the ``level_caps`` block inside the
progress file is not changed in shape, so earlier versions of the tracker keep
reading it. This module stores one switch per run and game in its own small
file and detects a level increase across the cap from recent live readings.
Loading a save state can look identical, so every crossing needs confirmation.
This module never reads or writes game memory.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

JSONDict = dict[str, Any]

FORMAT = 'progressive-tracker-level-caps-auto'
VERSION = 1
MAX_BYTES = 4096
# A level-up must be seen again in the next reading, and soon, before it counts.
CONFIRM_SECONDS = 30.0


def _key(p: Any) -> str | None:
    ec = p.get('encryption_constant')
    return f"{p.get('origin_version', 33)}:{ec}" if type(ec) is int else None


def party_levels(party: Any) -> dict[str, JSONDict]:
    """Valid, hatched party members of a reading, by specimen key."""
    result: dict[str, JSONDict] = {}
    for p in party if isinstance(party, list) else []:
        if not isinstance(p, dict) or p.get('egg') or p.get('checksum_valid') is not True:
            continue
        key, level = _key(p), p.get('level')
        if key is None or type(level) is not int or not 1 <= level <= 100:
            continue
        result[key] = {'level': level, 'name': str(p.get('nickname') or p.get('species') or 'Pokémon')[:40]}
    return result


class LevelUpWatcher:
    """Finds confirmed level increases across the cap between recent live readings.

    A level-up counts only when the same specimen was in the party in the
    previous live reading with a level at or below the cap, is now above it,
    and the next reading confirms it. Loading a team that is already above the
    cap, swapping party members, reconnecting or changing game never counts:
    the first reading after any interruption only sets the baseline.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.previous: dict[str, JSONDict] | None = None
        self.pending: JSONDict | None = None
        self.previous_at: float | None = None

    def reset(self) -> None:
        self.previous = None
        self.pending = None
        self.previous_at = None

    def observe(self, party: Any, cap: int | None) -> JSONDict | None:
        """Feed one live reading. Returns ``{'key','name','from','to','cap'}`` once a crossing is confirmed."""
        current = party_levels(party)
        now_at = self.clock()
        previous_at, self.previous_at = self.previous_at, now_at
        previous, self.previous = self.previous, current
        pending, self.pending = self.pending, None
        if (previous is None or cap is None or previous_at is None
                or now_at - previous_at > CONFIRM_SECONDS):
            return None
        # Check the whole team before confirming a previously observed crossing.
        if set(current) != set(previous) or any(current[key]['level'] < previous[key]['level'] for key in current):
            return None
        if pending is not None:
            now = current.get(pending['key'])
            # Confirmed: same specimen, same cap, still above it, read again in time.
            if (now is not None and pending['cap'] == cap and now['level'] >= pending['to']
                    and now_at - pending['seen'] <= CONFIRM_SECONDS):
                return {k: pending[k] for k in ('key', 'name', 'from', 'to', 'cap')}
        for key, now in current.items():
            before = previous.get(key)
            if before is not None and before['level'] <= cap < now['level']:
                self.pending = {'key': key, 'name': now['name'], 'from': before['level'], 'to': now['level'],
                                'cap': cap, 'seen': now_at}
                # Keep the pre-level-up baseline so the confirmation compares the same crossing.
                self.previous = {**current, key: before}
                break
        return None


class LevelCapsAuto:
    """The per-run, per-game switch (off by default) and the last automatic event of this session."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.enabled = False
        self.read_only = False
        self.event: JSONDict | None = None
        self.watcher = LevelUpWatcher()
        try:
            if self.path.is_file() and self.path.stat().st_size <= MAX_BYTES:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if isinstance(data, dict) and data.get('format') == FORMAT and type(data.get('version')) is int:
                    if data['version'] > VERSION:
                        # Written by a newer tracker: left untouched and off here.
                        self.read_only = True
                    elif type(data.get('enabled')) is bool:
                        self.enabled = data['enabled']
        except (OSError, ValueError):
            pass

    def check_writable(self) -> None:
        if self.read_only:
            raise ValueError('El avance automático de esta partida lo configuró una versión más nueva del tracker; '
                             'no se modifica aquí.')

    def set_enabled(self, enabled: Any) -> bool:
        if type(enabled) is not bool:
            raise ValueError('Indica si el avance automático se activa o se desactiva.')
        self.check_writable()
        if enabled == self.enabled:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.tmp')
        temporary.write_text(json.dumps({'format': FORMAT, 'version': VERSION, 'enabled': enabled,
                                         'updated_at': datetime.now(timezone.utc).isoformat()}), encoding='utf-8')
        os.replace(temporary, self.path)
        self.enabled = enabled
        # Turning it on never acts on what is already on screen: start from a fresh baseline.
        self.watcher.reset()
        self.event = None
        return True

    def view(self) -> JSONDict:
        return {'enabled': self.enabled, 'read_only': self.read_only,
                'event': None if self.event is None else dict(self.event)}

    def decide(self, party: Any, caps: JSONDict) -> JSONDict | None:
        """One live reading plus the current caps view -> an event to apply, or None.

        Every crossing suggests the next stage. Restoring a save state with the
        same team looks like a level-up, so the player must confirm. At most one
        event per reading; decreasing caps have their own explanation.
        """
        usable = self.enabled and caps.get('status') == 'ok' and caps.get('current_index') is not None
        crossing = self.watcher.observe(party, caps.get('current_cap') if usable else None)
        if crossing is None:
            return None
        stages, index = caps['stages'], caps['current_index']
        if index + 1 >= len(stages):
            return None
        current, following = stages[index], stages[index + 1]
        return {'id': secrets.token_hex(6), 'kind': 'suggest',
                'reason': 'decreasing_cap' if following['cap'] < current['cap'] else 'unverified_level_up',
                'at': datetime.now(timezone.utc).isoformat(), 'pokemon': crossing['name'],
                'from_level': crossing['from'], 'to_level': crossing['to'],
                'from_stage': {'id': current['id'], 'name': current['name'], 'cap': current['cap']},
                'to_stage': {'id': following['id'], 'name': following['name'], 'cap': following['cap']}}
