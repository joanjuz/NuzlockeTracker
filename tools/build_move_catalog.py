"""Build offline USUM reference data from PokeAPI CSV exports."""
import csv,json,re
from pathlib import Path
SOURCE=Path('/tmp/tracker-move-source')
OUTPUT=Path(__file__).resolve().parent.parent/'data'/'MoveDetails_USUM.json'
def read(name):return list(csv.DictReader((SOURCE/name).open(encoding='utf-8')))
def number(v):return int(v) if v else None
versions={int(r['id']):int(r['order']) for r in read('version_groups.csv')}
types={int(r['type_id']):r['name'] for r in read('type_names.csv') if r['local_language_id']=='7'}
names={int(r['move_id']):r['name'] for r in read('move_names.csv') if r['local_language_id']=='7'}
pp_source=Path('/tmp/MoveInfo7.cs').read_text()
pp7=[int(v) for v in re.findall(r'\b\d+\b',pp_source.split('PP =>')[1].split('[')[1].split(']')[0])]
changes={}
for r in read('move_changelog.csv'):
 if versions[int(r['changed_in_version_group_id'])]>versions[18]:changes.setdefault(int(r['move_id']),[]).append(r)
flavor={}
for r in read('move_flavor_text.csv'):
 if r['language_id']!='7':continue
 order=versions[int(r['version_group_id'])]
 if order>versions[18]:continue
 key=int(r['move_id'])
 if key not in flavor or order>flavor[key][0]:flavor[key]=(order,' '.join(r['flavor_text'].split()))
moves={}
for row in read('moves.csv'):
 id=int(row['id'])
 if not 1<=id<=728:continue
 # Each change stores the values before that version. Rewind newer changes.
 for change in sorted(changes.get(id,[]),key=lambda r:versions[int(r['changed_in_version_group_id'])],reverse=True):
  for field in ('type_id','power','pp','accuracy','priority','effect_chance'):
   if change.get(field):row[field]=change[field]
 moves[str(id)]={'id':id,'name':names.get(id,row['identifier']),'type':types[int(row['type_id'])],'category':{'1':'Estado','2':'Físico','3':'Especial'}[row['damage_class_id']],
  'power':number(row['power']),'pp':pp7[id],'accuracy':number(row['accuracy']),'priority':number(row['priority']),
  'effect_chance':number(row['effect_chance']),'description':flavor.get(id,(0,'Descripción no disponible en español para esta generación.'))[1],
  'source':'PokéAPI / PKHeX · Ultra Sun / Ultra Moon','wikidex_url':'https://www.wikidex.net/wiki/'+names.get(id,row['identifier']).replace(' ','_')}
OUTPUT.write_text(json.dumps({'schema_version':1,'game':'Ultra Moon 1.0','moves':moves},ensure_ascii=False,indent=2),encoding='utf-8')
print(len(moves),'movimientos; descripciones en español:',len([m for m in moves.values() if not m['description'].startswith('Descripción no disponible')]))
