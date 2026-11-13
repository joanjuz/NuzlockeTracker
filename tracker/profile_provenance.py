"""Optional historical recipe provenance. Informational only; no executable configuration."""
import copy
import json
import re

MAX_BLOCK_BYTES = 16 * 1024
SECTION = re.compile(r'(actions|manual|options)/[a-z0-9-]{1,80}\Z')
SHA256 = re.compile(r'[0-9A-F]{64}\Z')


def _object(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError('Campos de procedencia no válidos.')
    return value


def _text(value, maximum):
    if (not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in '/\\:' for c in value)):
        raise ValueError('Texto de procedencia no válido.')
    return value


def validated_profile_provenance(block, game_id):
    """Validate only v1. The caller isolates failure from the main DGD and other blocks."""
    _object(block, ['version', 'status', 'currentMatch', 'subsequentChanges', 'gameId', 'profile', 'sections'])
    if type(block.get('version')) is not int or block['version'] != 1:
        raise ValueError('Versión de procedencia no compatible.')
    if (block.get('status') != 'historical' or block.get('currentMatch') != 'not-verified'
            or block.get('subsequentChanges') not in ('recorded', 'none-recorded')
            or block.get('gameId') != game_id):
        raise ValueError('Estado o juego de procedencia no compatible.')
    profile = _object(block.get('profile'), ['format', 'version', 'name', 'author', 'recipeSha256'])
    if (profile.get('format') != 'definitive-randomizer-profile' or type(profile.get('version')) is not int
            or profile['version'] != 1):
        raise ValueError('Formato de perfil no compatible.')
    _text(profile.get('name'), 120)
    if 'author' in profile:
        _text(profile['author'], 80)
    if not isinstance(profile.get('recipeSha256'), str) or not SHA256.fullmatch(profile['recipeSha256']):
        raise ValueError('Huella declarada no válida.')
    sections = block.get('sections')
    if (not isinstance(sections, list) or not 1 <= len(sections) <= 64
            or any(not isinstance(s, str) or len(s) > 90 or not SECTION.fullmatch(s) for s in sections)
            or sections != sorted(set(sections))):
        raise ValueError('Secciones no válidas o sin orden único.')
    if len(json.dumps(block, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > MAX_BLOCK_BYTES:
        raise ValueError('Procedencia demasiado grande.')
    return copy.deepcopy(block)


def profile_provenance_summary(document):
    if not isinstance(document, dict) or 'profileProvenance' not in document:
        return {'state': 'absent', 'reason': 'El archivo no incluye procedencia de perfil.'}
    block = document['profileProvenance']
    try:
        if len(json.dumps(block, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > MAX_BLOCK_BYTES:
            raise ValueError('Procedencia demasiado grande.')
        if isinstance(block, dict) and type(block.get('version')) is int and block['version'] > 1:
            return {'state': 'ignored', 'reason': 'La procedencia de perfil usa una versión más nueva y no se puede mostrar. Los demás datos DGD siguen disponibles.'}
        valid = validated_profile_provenance(block, document['game']['id'])
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        return {'state': 'ignored', 'reason': 'La procedencia de perfil no es válida y se ignora. Los demás datos DGD siguen disponibles.'}
    return {'state': 'historical', 'name': valid['profile']['name'], 'author': valid['profile'].get('author'),
            'gameId': valid['gameId'], 'sections': valid['sections'], 'recipeSha256': valid['profile']['recipeSha256'],
            'currentMatch': 'not-verified', 'subsequentChanges': valid['subsequentChanges']}
