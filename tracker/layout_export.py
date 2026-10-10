"""Six stable image slots for OBS, preserving both static PNG and animated GIF.

Local-only layout output; all six slots always have PNG + GIF counterparts.
Never mutate source sprites, game saves, emulator memory or cloud credentials.
"""
from __future__ import annotations

import io
import os
import re
import unicodedata
import struct
import sys
import threading
import time
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from .progress import pokemon_key

# PokeAPI sprite IDs for Gen7 Alolan variants. Do not show the Kanto sprite
# when an Alolan species has been detected.
ALOLA_SPRITES = {
    19: 10091, 20: 10092, 26: 10100, 27: 10101, 28: 10102,
    37: 10103, 38: 10104, 50: 10105, 51: 10106, 52: 10107,
    53: 10108, 74: 10109, 75: 10110, 76: 10111, 88: 10112,
    89: 10113, 103: 10114, 105: 10115,
}
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
GIF_MAGIC = (b'GIF87a', b'GIF89a')
MAX_GIF_BYTES = 5_000_000
MAX_GIF_FRAMES = 120
MAX_GIF_FRAME_PIXELS = 512 * 512
MAX_GIF_TOTAL_PIXELS = 12_000_000


def _chunk(name, data):
    return struct.pack('>I', len(data)) + name + data + struct.pack(
        '>I', zlib.crc32(name + data) & 0xffffffff)


def blank_sprite(size=96):
    """Fixed transparent canvas avoids OBS resizing a slot when it is empty."""
    raw = b''.join(b'\x00' + bytes(size * 4) for _ in range(size))
    return (PNG_MAGIC + _chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(raw, 9)) + _chunk(b'IEND', b''))


BLANK_PNG = blank_sprite()


def sprite_id(mon):
    if not isinstance(mon, dict):
        return None
    species = mon.get('species_id')
    if type(species) is not int or not 1 <= species <= 807 or mon.get('egg'):
        return None
    if mon.get('form') == 1 and species in ALOLA_SPRITES:
        return ALOLA_SPRITES[species]
    return species


def validate_png(data):
    if not isinstance(data, bytes) or not (33 <= len(data) <= 8_000_000):
        raise ValueError('Sprite PNG inválido')
    if not data.startswith(PNG_MAGIC) or data[12:16] != b'IHDR':
        raise ValueError('Cabecera PNG inválida')
    width, height = struct.unpack_from('>II', data, 16)
    if not (1 <= width <= 2048 and 1 <= height <= 2048 and width * height <= 2_500_000):
        raise ValueError('Dimensiones PNG inválidas')
    return data


def grayscale_png(data):
    """Desaturate an output PNG, preserving alpha and never editing its source."""
    validate_png(data)
    with Image.open(io.BytesIO(data)) as src:
        rgba = src.convert('RGBA')
        gray = ImageOps.grayscale(rgba)
        result = Image.merge('RGBA', (gray, gray, gray, rgba.getchannel('A')))
        out = io.BytesIO()
        result.save(out, format='PNG')
    return validate_png(out.getvalue())



def validate_gif(data):
    """Validate small finite GIFs before decoding user-generated animations."""
    if not isinstance(data, bytes) or len(data) < 19 or len(data) > MAX_GIF_BYTES:
        raise ValueError('GIF personalizado demasiado grande o inválido')
    if not data.startswith(GIF_MAGIC):
        raise ValueError('El archivo no contiene un GIF')
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            count = image.n_frames
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


def animation_frames(data, dead=False):
    validate_gif(data)
    frames = []
    durations = []
    with Image.open(io.BytesIO(data)) as animation:
        for index in range(animation.n_frames):
            animation.seek(index)
            rgba = animation.convert('RGBA')
            if dead:
                gray = ImageOps.grayscale(rgba)
                rgba = Image.merge('RGBA', (gray, gray, gray, rgba.getchannel('A')))
            frames.append(rgba)
            duration = int(animation.info.get('duration', 100) or 100)
            durations.append(max(20, min(duration, 5000)))
    return frames, durations


def gif_to_outputs(data, dead=False):
    """Produce an animated GIF + its first PNG frame for legacy OBS layouts."""
    frames, durations = animation_frames(data, dead=dead)
    first_png = io.BytesIO()
    frames[0].save(first_png, format='PNG')
    output = io.BytesIO()
    # GIF only has binary transparency, unlike PNG. Re-encode all frames
    # with loop=0 so OBS loops continuously, including grayscale dead sprites.
    frames[0].save(output, format='GIF', save_all=True,
                   append_images=frames[1:], duration=durations,
                   loop=0, disposal=2)
    return validate_png(first_png.getvalue()), validate_gif(output.getvalue())


def png_to_gif(data):
    """Single-frame GIF gives OBS a fixed .gif path for nonanimated species."""
    validate_png(data)
    with Image.open(io.BytesIO(data)) as src:
        output = io.BytesIO()
        src.convert('RGBA').save(output, format='GIF', loop=0)
        return validate_gif(output.getvalue())


def safe_sprite_stem(value):
    """Normalize friendly names to safe file stems, never to paths."""
    if not isinstance(value, str):
        return ''
    base = unicodedata.normalize('NFKD', value).casefold()
    base = ''.join(c for c in base if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '-', base).strip('-')[:80]


CUSTOM_EXTENSIONS = ('.gif', '.webp', '.png', '.apng', '.jpg', '.jpeg', '.bmp')


def custom_media_names(mon, ident):
    """Allow National Dex, padded ID, names, regional variants and shiny names.

    All returned names are flat filenames; files never leave the custom directory.
    GIF/WebP animation takes priority for each *identity*, then lossless PNG.
    """
    species = mon['species_id']
    padded = f'{species:03d}'
    base = [str(species), padded, str(ident)]
    alias = safe_sprite_stem(mon.get('species') or '')
    if alias:
        base.append(alias)
    if mon.get('form') == 1 and species in ALOLA_SPRITES:
        base = ([f'{species}-alola', f'{padded}-alola',
                 f'{species}_alola', f'{padded}_alola',
                 f'{alias}-alola' if alias else '',
                 str(ident)] + base)
    form = mon.get('form')
    if type(form) is int and form > 0 and not (form == 1 and species in ALOLA_SPRITES):
        base = [f'{species}-{form}', f'{padded}-{form}',
                f'{alias}-{form}' if alias else ''] + base
    if mon.get('shiny') or mon.get('is_shiny'):
        base = ([stem+ending for stem in base for ending in ('-shiny','_shiny','-s')]
                + base)
    stems = list(dict.fromkeys(stem for stem in base if stem))
    # Preserve old behaviour: animation before any static image.
    return tuple(stem+ext for ext in CUSTOM_EXTENSIONS for stem in stems)


def custom_names(mon, ident):
    """Species National Dex ID; regional names override their numeric form ID."""
    species = mon['species_id']
    if mon.get('form') == 1 and species in ALOLA_SPRITES:
        return (f'{species}-alola.png', f'{ident}.png')
    return (f'{species}.png',)


def normalize_custom_sprite(data, ext):
    """Decode bounded user artwork; keep native PNG precision and WebP animation.

    Accepted: PNG/APNG, animated GIF/WebP, static WebP/JPEG/BMP.
    No SVG (scripts/external resource references are unsuitable for OBS).
    """
    if not isinstance(data, bytes) or len(data)>8_000_000:
        raise ValueError('Imagen personalizada demasiado grande')
    if ext not in CUSTOM_EXTENSIONS:
        raise ValueError('Formato de sprite no admitido')
    try:
        with Image.open(io.BytesIO(data)) as im:
            width,height=im.size
            count=getattr(im,'n_frames',1)
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


def animation_to_webp(data, kind, dead=False):
    """Animated RGBA to WebP, lossless and without palette quantization."""
    frames=[];durations=[]
    with Image.open(io.BytesIO(data)) as im:
        for n in range(im.n_frames):
            im.seek(n)
            image=im.convert('RGBA')
            if dead:
                gray=ImageOps.grayscale(image)
                image=Image.merge('RGBA',(gray,gray,gray,image.getchannel('A')))
            frames.append(image)
            durations.append(max(20,min(int(im.info.get('duration',100) or 100),5000)))
    first=io.BytesIO();frames[0].save(first,format='PNG')
    out=io.BytesIO()
    frames[0].save(out,format='WEBP',save_all=True,append_images=frames[1:],
                   duration=durations,loop=0,lossless=True,quality=100,method=4)
    return validate_png(first.getvalue()),out.getvalue()


def fetch_sprite(identifier):
    if not 1 <= identifier <= 10115:
        raise ValueError('Identificador fuera de rango')
    url = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/' + str(identifier) + '.png'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=8) as response:
        return validate_png(response.read(500_001))


def layout_directory(home, profile='principal', executable=None, frozen=None):
    """Portable next-to-EXE when writable, otherwise persistent AppData fallback."""
    home = Path(home)
    if frozen is None:
        frozen = getattr(sys, 'frozen', False)
    if frozen:
        parent = Path(executable or sys.executable).resolve().parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            test = parent / '.layout-write-test'
            with open(test, 'wb') as f:
                f.write(b'x')
            test.unlink()
            base = parent / 'layout'
        except OSError:
            base = home / 'layout'
    else:
        base = home / 'layout'
    return base if profile == 'principal' else base / 'perfil_2'


class PartyLayoutExporter:
    def __init__(self, service, directory, cache_dir=None, downloader=fetch_sprite, bundled=None, custom_dir=None):
        self.service = service
        self.directory = Path(directory)
        self.cache = Path(cache_dir or self.directory.parent / 'sprite-cache')
        self.custom = Path(custom_dir or self.directory.parent / 'sprites_personalizados')
        self.bundled = Path(bundled or (Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'data' / 'sprites'))
        self.downloader = downloader
        self.stop = threading.Event()
        self.thread = None
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='layout-sprite')
        self.futures = {}
        self.retry_after = {}
        self.slots = [None] * 6
        self.contents = [None] * 6
        self.gif_contents = [None] * 6
        self.render_signatures = [None] * 6
        self.media_types = [None] * 6
        self.custom_cache = {}  # path -> (mtime_ns, size, validated media or None)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.custom.mkdir(parents=True, exist_ok=True)
        # Guarantee six files immediately, including slots that are empty.
        self.blank_gif = png_to_gif(BLANK_PNG)
        for index in range(6):
            self.write_slot(index, BLANK_PNG)
            self.write_gif_slot(index, self.blank_gif)
            self.write_media_type(index, 'png')

    def write_slot(self, index, data):
        if self.contents[index] == data:
            return
        name = self.directory / f'pokemon_{index+1}.png'
        tmp = self.directory / f'.pokemon_{index+1}.{os.getpid()}.tmp'
        try:
            tmp.write_bytes(data)
            os.replace(tmp, name)
            self.contents[index] = data
        finally:
            if tmp.exists():
                tmp.unlink()

    def write_gif_slot(self, index, data):
        if self.gif_contents[index] == data:
            return
        name = self.directory / f'pokemon_{index+1}.gif'
        tmp = self.directory / f'.pokemon_{index+1}.{os.getpid()}.gif.tmp'
        try:
            tmp.write_bytes(data)
            os.replace(tmp, name)
            self.gif_contents[index] = data
        finally:
            if tmp.exists():
                tmp.unlink()

    def write_media_type(self,index,kind):
        if self.media_types[index]==kind:
            return
        target=self.directory/f'pokemon_{index+1}.media'
        tmp=self.directory/f'.pokemon_{index+1}.{os.getpid()}.media.tmp'
        try:
            tmp.write_text(kind,encoding='ascii')
            os.replace(tmp,target)
            self.media_types[index]=kind
        finally:
            tmp.unlink(missing_ok=True)

    def write_webp_slot(self,index,data):
        target=self.directory/f'pokemon_{index+1}.webp'
        tmp=self.directory/f'.pokemon_{index+1}.{os.getpid()}.webp.tmp'
        try:
            tmp.write_bytes(data)
            os.replace(tmp,target)
        finally:
            tmp.unlink(missing_ok=True)

    def publish(self, index, ident, source, animated=False, dead=False):
        """Expose the original visual format, not an indexed GIF for every PNG."""
        signature = (ident, dead, animated, source)
        if self.render_signatures[index] == signature:
            return
        if animated == 'webp' or animated == 'apng':
            png, webp=animation_to_webp(source,animated,dead=dead)
            self.write_slot(index,png)
            # Legacy GIF slot preserved for existing OBS setups (first frame).
            self.write_gif_slot(index,png_to_gif(png))
            self.write_webp_slot(index,webp)
            self.write_media_type(index,'webp')
        elif animated is True or animated == 'gif':
            png,gif=gif_to_outputs(source,dead=dead)
            self.write_slot(index,png)
            self.write_gif_slot(index,gif)
            self.write_media_type(index,'gif')
        else:
            png=self.render_sprite(source,dead)
            self.write_slot(index,png)
            self.write_gif_slot(index,png_to_gif(png))
            self.write_media_type(index,'png')
        self.render_signatures[index]=signature

    def clear_slot(self,index):
        self.render_signatures[index]=None
        self.write_slot(index,BLANK_PNG)
        self.write_gif_slot(index,self.blank_gif)
        self.write_media_type(index,'png')

    def local_sprite(self, ident):
        for folder in (self.cache, self.bundled):
            candidate = folder / f'{ident}.png'
            if candidate.is_file():
                try:
                    return validate_png(candidate.read_bytes())
                except (OSError, ValueError):
                    continue
        return None

    def custom_media(self,mon,ident):
        if not self.custom.is_dir():return None
        # Resolve case-insensitively, including names such as Pikachu.PNG.
        # Only files directly in the known sprites_personalizados directory.
        available={}
        try:
            for child in self.custom.iterdir():
                if child.is_file() and not child.is_symlink():
                    available.setdefault(child.name.casefold(),child)
        except OSError:
            return None
        for name in custom_media_names(mon,ident):
            candidate=available.get(name.casefold())
            if candidate is None:continue
            try:
                stat=candidate.stat()
                signature=(stat.st_mtime_ns,stat.st_size)
                cached=self.custom_cache.get(candidate)
                if cached and cached[0]==signature:
                    if cached[1] is not None:return cached[1]
                    continue
                media=None
                if stat.st_size<=8_000_000:
                    try:
                        media=normalize_custom_sprite(candidate.read_bytes(),
                                                       candidate.suffix.lower())
                    except (OSError,ValueError):
                        pass
                if len(self.custom_cache)>96:self.custom_cache.clear()
                self.custom_cache[candidate]=(signature,media)
                if media is not None:return media
            except OSError:
                self.custom_cache.pop(candidate,None)
        return None

    def render_sprite(self, data, dead):
        return grayscale_png(data) if dead else data

    def download_and_store(self, ident):
        data = validate_png(self.downloader(ident))
        self.cache.mkdir(parents=True, exist_ok=True)
        tmp = self.cache / f'.{ident}.{os.getpid()}.tmp'
        try:
            tmp.write_bytes(data)
            os.replace(tmp, self.cache / f'{ident}.png')
        finally:
            if tmp.exists():
                tmp.unlink()
        return data

    def refresh(self):
        state = self.service.snapshot()
        party = state.get('party') or []
        deaths = (state.get('progress') or {}).get('deaths') or {}
        now = time.monotonic()
        for i in range(6):
            mon = party[i] if i < len(party) else None
            ident = sprite_id(mon)
            if ident is None:
                self.slots[i] = None
                self.clear_slot(i)
                continue
            dead = pokemon_key(mon) in deaths
            # User PNG/GIF changes are picked up on the next refresh.
            # Animation conversion is cached when all inputs are unchanged.
            custom = self.custom_media(mon, ident)
            if custom is not None:
                raw,kind=custom
                self.slots[i]=ident
                self.publish(i,ident,raw,animated=kind if kind!='png' else False,dead=dead)
                continue
            local = self.local_sprite(ident)
            if local is not None:
                self.slots[i] = ident
                self.publish(i, ident, local, dead=dead)
                continue
            if self.slots[i] != ident:
                self.slots[i] = ident
                self.clear_slot(i)
            future = self.futures.get(ident)
            if future and future.done():
                del self.futures[ident]
                try:
                    # Only use the downloaded sprite for the species currently
                    # occupying this slot; keep custom priority intact.
                    self.publish(i, ident, future.result(), dead=dead)
                except Exception:
                    self.retry_after[ident] = now + 30
            elif future is None and now >= self.retry_after.get(ident, 0):
                self.futures[ident] = self.pool.submit(self.download_and_store, ident)

    def run(self):
        while not self.stop.is_set():
            try:
                self.refresh()
            except Exception:
                # Layout is optional: no failure may stop the RAM or cloud worker.
                pass
            with self.service.condition:
                self.service.condition.wait(timeout=0.5)

    def start(self):
        if self.thread is not None:
            return
        self.thread = threading.Thread(target=self.run, name='layout-export', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        with self.service.condition:
            self.service.condition.notify_all()
        if self.thread:
            self.thread.join(timeout=3)
        self.pool.shutdown(wait=False, cancel_futures=True)
