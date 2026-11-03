"""Overlays de OBS servidos por el tracker local (paquete).

- settings: valores por defecto y validación de ajustes.
- assets: fuentes, PNG importados, imagen de muerte e importación de sprites.
- graveyard: cementerio y estadísticas de la partida.
- presets: perfiles de configuración y exportación/importación.
- manager: OverlayManager, que une todo y genera el estado público.
"""
from .manager import OverlayManager
from .settings import ALLOWED, DEFAULT, PALETTE, VALID_FONTS, font_is_valid, validated_settings

__all__ = ['OverlayManager', 'DEFAULT', 'ALLOWED', 'PALETTE', 'VALID_FONTS', 'font_is_valid', 'validated_settings']
