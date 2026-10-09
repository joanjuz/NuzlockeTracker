import urllib.request,concurrent.futures
from pathlib import Path
base='https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'
names=['moves.csv','move_changelog.csv','move_names.csv','move_flavor_text.csv','type_names.csv','version_groups.csv','languages.csv']
root=Path('/tmp/tracker-move-source');root.mkdir(exist_ok=True)
def fetch(name):
 data=urllib.request.urlopen(base+name,timeout=30).read();(root/name).write_bytes(data);return name,len(data)
urllib.request.urlretrieve('https://raw.githubusercontent.com/kwsch/PKHeX/master/PKHeX.Core/Moves/MoveInfo7.cs','/tmp/MoveInfo7.cs')
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as ex:
 for r in ex.map(fetch,names):print(r)
