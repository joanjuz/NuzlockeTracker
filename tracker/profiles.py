"""Game profiles are independent of emulator connectors."""
from dataclasses import dataclass

@dataclass(frozen=True)
class GameProfile:
    name: str
    emulator: str
    party_address: int
    slot_stride: int
    slot_size: int
    verified: bool = False
    box_address: int = 0x33015AB0
    generation: int = 7

# Validated by captura1.bin checksums and user confirmation for this ROM.
# Source: kcblack42/Citra-Tracker-v2/citra-updater.py (getaddresses/read_party).
ULTRA_MOON_10 = GameProfile(
    name='Ultra Moon 1.0', emulator='Lime3DS 2119.1',
    party_address=0x33F7FA44, slot_stride=484, slot_size=484, verified=True,
)

def capture_party(reader, profile=ULTRA_MOON_10):
    """Bounded diagnostic snapshot, without claiming decoded/consistent Pokémon."""
    return reader.read(profile.party_address, profile.slot_stride * 5 + 494)

# Upstream groups Ultra Sun/Moon at the same party base. Hardware validation pending.
ULTRA_SUN_10 = GameProfile('Ultra Sun 1.0', 'Lime3DS 2119.1', 0x33F7FA44, 484, 484)
# Legacy Citra-Tracker-v2 Gen6 candidates (Citra on 1.0 game versions).
# These are NOT validated for Azahar/Lime3DS or updated ROMs yet.
# Gen6 box base candidates: 0x08C861C8 (XY), 0x08C9E134 (ORAS).
# Reference: samabr85/Gen6CTRPFrameworkOverhauled Sources/PKHeX.cpp
# DetermineSpeciesPointer(). Runtime checksum and repeated-read checks required.
POKEMON_X_10 = GameProfile('Pokémon X 1.0','Citra (experimental)',0x08CE1CE8,484,484,box_address=0x08C861C8,generation=6)
POKEMON_Y_10 = GameProfile('Pokémon Y 1.0','Citra (experimental)',0x08CE1CE8,484,484,box_address=0,generation=6)
OMEGA_RUBY_10 = GameProfile('Omega Ruby 1.0','Citra (experimental)',0x08CF727C,484,484,box_address=0,generation=6)
ALPHA_SAPPHIRE_10 = GameProfile('Alpha Sapphire 1.0','Citra (experimental)',0x08CF727C,484,484,box_address=0,generation=6)
GEN6_GAMES = (POKEMON_X_10.name, POKEMON_Y_10.name, OMEGA_RUBY_10.name, ALPHA_SAPPHIRE_10.name)
PROFILES = {p.name: p for p in (ULTRA_MOON_10, ULTRA_SUN_10,
                              POKEMON_X_10,POKEMON_Y_10,OMEGA_RUBY_10,ALPHA_SAPPHIRE_10)}
BATTLE_CANDIDATES = {
    'battle_runtime': 0x33F7FA44 - 0x3f760d4 - 34 - 496 - 64,
    'wild_party': 0x33F7FA44 - 30000000 + 7008668,
    'trainer_party': 0x33F7FA44 - 30000000 + 7110648,
}
