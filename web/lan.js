'use strict';
let TOKEN = '';
try { TOKEN = decodeURIComponent(location.hash.substring(1)); } catch (_) { TOKEN = ''; }
const status = document.getElementById('status');
const teams = {A: document.getElementById('team-a'), B: document.getElementById('team-b')};
const slots = ['A-SUN','A-MOON','B-SUN','B-MOON'];
const panels = {};
function node(tag, cls, text) {const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
for (const slot of slots) {
  const card=node('article','player');const head=node('div','playerhead');
  const left=node('div');const name=node('div','name',slot);const game=node('div','info');left.append(name,game);
  const badge=node('div','badge off','Sin conexión');head.append(left,badge);
  const mons=node('div','mons');card.append(head,mons);teams[slot[0]].append(card);
  panels[slot]={name,game,badge,mons};
}
function renderMon(p) {
  const card=node('div','mon'+(p&&p.hp===0?' ko-mon':''));
  if (!p){card.append(node('div','empty','—'));return card;}
  const img=document.createElement('img');img.alt=p.species||('Pokémon #'+p.species_id);
  img.src='https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/'+p.species_id+'.png';
  img.addEventListener('error',()=>{img.replaceWith(node('div','empty','#'+p.species_id));},{once:true});
  card.append(img,node('div','nickname',p.nickname||p.species||('#'+p.species_id)));
  const bar=node('div','hpbar');const fill=node('span',p.hp===0?'ko':p.hp*2<=p.max_hp?'warn':'');
  fill.style.width=(p.hp/p.max_hp*100)+'%';bar.append(fill);card.append(bar,node('div','hint',p.hp+'/'+p.max_hp+' PS · Nv.'+p.level));
  return card;
}
function renderRoom(room) {
  if (room.mode!=='soul-link-2v2-lan'||!Array.isArray(room.players))throw new Error('Formato de sala incompatible');
  for(const p of room.players){const panel=panels[p.slot];if(!panel)continue;
    panel.name.textContent=p.name;panel.game.textContent=p.game;
    panel.badge.className='badge '+(p.connected?'ok':'off');
    panel.badge.textContent=p.connected?(p.battle_hp?'En combate':'En línea'):(p.last_seen?'Tracker desconectado':'Sin señal');
    panel.mons.replaceChildren(...(p.connected&&Array.isArray(p.party)?p.party:Array(6).fill(null)).map(renderMon));
  }
}
async function refresh() {
  if(!TOKEN){status.textContent='Falta el código de espectador al final del enlace (#código).';return;}
  try {
    const response=await fetch('/api/room',{headers:{Authorization:'Bearer '+TOKEN},cache:'no-store'});
    if(!response.ok)throw new Error(response.status===403?'Clave de espectador incorrecta':'Sala no disponible');
    renderRoom(await response.json());status.textContent='Sala activa · actualización cada 2 segundos';
  }catch(e){status.textContent='Sin conexión: '+e.message;}
}
refresh();setInterval(refresh,2000);
