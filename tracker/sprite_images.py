"""Validacion y conversion de imagenes de sprites (PNG, GIF, WebP, APNG).

Funciones puras sobre bytes: nunca leen ni escriben archivos, ni tocan la
partida, la memoria del emulador o credenciales. Las usan el exportador de
layout (tracker.layout_export), el overlay OBS y los sprites personalizados.
Cada nombre se sigue pudiendo importar desde tracker.layout_export.
"""
from __future__ import annotations

import io
import struct
import zlib

from PIL import Image, ImageOps, UnidentifiedImageError

PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
GIF_MAGIC = (b'GIF87a', b'GIF89a')
MAX_GIF_BYTES = 5_000_000
MAX_GIF_FRAMES = 120
MAX_GIF_FRAME_PIXELS = 512 * 512
MAX_GIF_TOTAL_PIXELS = 12_000_000
CUSTOM_EXTENSIONS = ('.gif', '.webp', '.png', '.apng', '.jpg', '.jpeg', '.bmp')


def _chunk(name: bytes, data: bytes) -> bytes:
    return struct.pack('>I', len(data)) + name + data + struct.pack(
        '>I', zlib.crc32(name + data) & 0xffffffff)


def blank_sprite(size: int = 96) -> bytes:
    """Fixed transparent canvas avoids OBS resizing a slot when it is empty."""
    raw = b''.join(b'\x00' + bytes(size * 4) for _ in range(size))
    return (PNG_MAGIC + _chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(raw, 9)) + _chunk(b'IEND', b''))


BLANK_PNG = blank_sprite()


def validate_png(data: object) -> bytes:
    if not isinstance(data, bytes) or not (33 <= len(data) <= 8_000_000):
        raise ValueError('Sprite PNG inválido')
    if not data.startswith(PNG_MAGIC) or data[12:16] != b'IHDR':
        raise ValueError('Cabecera PNG inválida')
    width, height = struct.unpack_from('>II', data, 16)
    if not (1 <= width <= 2048 and 1 <= height <= 2048 and width * height <= 2_500_000):
        raise ValueError('Dimensiones PNG inválidas')
    return data


def grayscale_png(data: bytes) -> bytes:
    """Desaturate an output PNG, preserving alpha and never editing its source."""
    validate_png(data)
    with Image.open(io.BytesIO(data)) as src:
        rgba = src.convert('RGBA')
        gray = ImageOps.grayscale(rgba)
        result = Image.merge('RGBA', (gray, gray, gray, rgba.getchannel('A')))
        out = io.BytesIO()
        result.save(out, format='PNG')
    return validate_png(out.getvalue())


def validate_gif(data: object) -> bytes:
    """Validate small finite GIFs before decoding user-generated animations."""
    if not isinstance(data, bytes) or len(data) < 19 or len(data) > MAX_GIF_BYTES:
        raise ValueError('GIF personalizado demasiado grande o inválido')
    if not data.startswith(GIF_MAGIC):
        raise ValueError('El archivo no contiene un GIF')
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            count: int = getattr(image, 'n_frames')  # GIF only; not in Pillow's stubs
            if (image.format != 'GIF' or not 1 <= width <= 512 or
                    not 1 <= height <= 512 or not 1 <= count <= MAX_GIF_FRAMES or
                    width * height * count > MAX_GIF_TOTAL_PIXELS):
                raise ValueError('GIF fuera de los límites de fotogramas o resolución')
            # Decoding now avoids accepting truncated files as valid custom assets.
            for index in range(count):
                image.seek(index)
                image.load()
    except (UnidentifiedImageError, OSError, EOFError) as exc:
        raise ValueError('GIF dañado o incompleto') from exc
    return data


def animation_frames(data: bytes, dead: bool = False) -> tuple[list[Image.Image], list[int]]:
    validate_gif(data)
    frames: list[Image.Image] = []
    durations: list[int] = []
    with Image.open(io.BytesIO(data)) as animation:
        for index in range(getattr(animation, 'n_frames')):
            animation.seek(index)
            rgba = animation.convert('RGBA')
            if dead:
                gray = ImageOps.grayscale(rgba)
                rgba = Image.merge('RGBA', (gray, gray, gray, rgba.getchannel('A')))
            frames.append(rgba)
            duration = int(animation.info.get('duration', 100) or 100)
            durations.append(max(20, min(duration, 5000)))
    return frames, durations


def gif_to_outputs(data: bytes, dead: bool = False) -> tuple[bytes, bytes]:
    """Produce an animated GIF + its first PNG frame for legacy OBS layouts."""
    frames, durations = animation_frames(data, dead=dead)
    first_png = io.BytesIO()
    frames[0].save(first_png, format='PNG')
    # Preserve original GIF palette, alpha and animation when it already
    # loops. Lossy recompression is reserved for grayscale dead Pokémon.
    if not dead:
        with Image.open(io.BytesIO(data)) as original:
            if original.info.get('loop')==0:
                return validate_png(first_png.getvalue()), validate_gif(data)
    output = io.BytesIO()
    frames[0].save(output, format='GIF', save_all=True,
                   append_images=frames[1:], duration=durations,
                   loop=0, disposal=2)
    return validate_png(first_png.getvalue()), validate_gif(output.getvalue())


def png_to_gif(data: bytes) -> bytes:
    """Single-frame GIF gives OBS a fixed .gif path for nonanimated species."""
    validate_png(data)
    with Image.open(io.BytesIO(data)) as src:
        output = io.BytesIO()
        rgba=src.convert('RGBA')
        # GIF is now only for legacy external links. The new browser overlay
        # renders the lossless PNG at the original resolution.
        if rgba.width>512 or rgba.height>512:
            rgba.thumbnail((512,512),resample=Image.Resampling.NEAREST)
        rgba.save(output, format='GIF', loop=0)
        return validate_gif(output.getvalue())


def normalize_custom_sprite(data: object, ext: str) -> tuple[bytes, str]:
    """Decode bounded user artwork; keep native PNG precision and WebP animation.

    Accepted: PNG/APNG, animated GIF/WebP, static WebP/JPEG/BMP.
    No SVG (scripts/external resource references are unsuitable for OBS).
    Returns (bytes, kind) with kind in 'gif', 'webp', 'apng' or 'png'.
    """
    if not isinstance(data, bytes) or len(data)>8_000_000:
        raise ValueError('Imagen personalizada demasiado grande')
    if ext not in CUSTOM_EXTENSIONS:
        raise ValueError('Formato de sprite no admitido')
    try:
        with Image.open(io.BytesIO(data)) as im:
            width,height=im.size
            count: int = getattr(im,'n_frames',1)
            if not (1<=width<=2048 and 1<=height<=2048 and
                    width*height<=2_500_000 and 1<=count<=120 and
                    width*height*count<=16_000_000):
                raise ValueError('Sprite supera los límites de imagen/animación')
            if count>1:
                if ext=='.gif':
                    return validate_gif(data),'gif'
                if ext not in ('.webp','.apng','.png'):
                    raise ValueError('Animación no admitida')
                # APNG/WebP animation stays high fidelity with alpha (not a GIF palette).
                for n in range(count):
                    im.seek(n)
                    im.load()
                return data, 'webp' if ext=='.webp' else 'apng'
            im.seek(0)
            rgba=im.convert('RGBA')
            if ext=='.png' and data.startswith(PNG_MAGIC):
                return validate_png(data),'png'
            output=io.BytesIO()
            rgba.save(output,format='PNG',optimize=True)
            return validate_png(output.getvalue()),'png'
    except (UnidentifiedImageError,OSError,EOFError,ValueError) as exc:
        raise ValueError('No se puede leer el sprite personalizado: '+str(exc)) from exc


def animation_to_webp(data: bytes, kind: str, dead: bool = False) -> tuple[bytes, bytes]:
    """Animated RGBA to WebP, lossless and without palette quantization."""
    frames: list[Image.Image] = []
    durations: list[int] = []
    with Image.open(io.BytesIO(data)) as im:
        for n in range(getattr(im, 'n_frames')):
            im.seek(n)
            image=im.convert('RGBA')
            if dead:
                gray=ImageOps.grayscale(image)
                image=Image.merge('RGBA',(gray,gray,gray,image.getchannel('A')))
            frames.append(image)
            durations.append(max(20,min(int(im.info.get('duration',100) or 100),5000)))
    first=io.BytesIO()
    frames[0].save(first,format='PNG')
    out=io.BytesIO()
    frames[0].save(out,format='WEBP',save_all=True,append_images=frames[1:],
                   duration=durations,loop=0,lossless=True,quality=100,method=4)
    if out.tell()>16_000_000:
        raise ValueError('Animación personalizada demasiado grande')
    return validate_png(first.getvalue()),out.getvalue()
