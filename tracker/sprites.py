"""Optional cached species sprites; tracker readings do not depend on downloads."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request
class SpriteCache:
    def __init__(self):
        self.directory=Path(__file__).resolve().parent.parent/'data'/'sprites'
        self.pool=ThreadPoolExecutor(max_workers=2);self.pending={};self.failed=set()
    def path(self,species):
        path=self.directory/f'{species}.png'
        if path.exists():return path
        if species in self.pending:
            future=self.pending[species]
            if future.done():
                try:future.result()
                except Exception:self.failed.add(species)
                del self.pending[species]
                if path.exists():return path
        elif species not in self.failed:
            self.pending[species]=self.pool.submit(self.download,species,path)
        return None
    def download(self,species,path):
        if not 1<=species<=807:raise ValueError('Especie inválida.')
        data=urllib.request.urlopen(f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{species}.png',timeout=8).read(200000)
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Sprite inválido.')
        self.directory.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp');temporary.write_bytes(data);temporary.replace(path)
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
