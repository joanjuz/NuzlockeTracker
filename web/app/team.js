'use strict';
// Team cards and top-bar mini team.
const labels=[['ATQ','Ataque'],['DEF','Defensa'],['ATE','At. esp.'],['DEE','Def. esp.'],['VEL','Velocidad']];
// Consume both halves of card activation, even when the dialog moves focus.
const cardActivationKeys=new Set();
function activatePartyCard(event,node){
  if(event.key!=='Enter'&&event.key!==' ')return;
  event.preventDefault();event.stopPropagation();
  if(event.repeat)return;
  cardActivationKeys.add(event.key);node.click();
}
document.addEventListener('keyup',event=>{
  if(!cardActivationKeys.delete(event.key))return;
  event.preventDefault();event.stopPropagation();
},true);
window.addEventListener('blur',()=>cardActivationKeys.clear());
const nodes=Array.from({length:6},(_,i)=>{const node=document.createElement('article');node.className='card empty';node.innerHTML=`<strong>0${i+1}</strong><p>Esperando equipo</p>`;node.tabIndex=0;node.setAttribute('role','button');node.setAttribute('aria-label',`Abrir Pokémon ${i+1}`);node.onclick=()=>openDetail(state?.party[i],`party:${i}`);node.onkeydown=e=>activatePartyCard(e,node);$('party').append(node);return node});
function portrait(p){const id=spriteId(p.species_id);return `<div class="portrait"><img src="/sprites/${id}.png" data-fallback="${id}" alt="${esc(p.species)}" loading="lazy"><div class="sprite-fallback" hidden>${num(p.species_id)}</div><div><h2>${esc(p.nickname||p.species)}</h2><p>${esc(p.species)} · ${p.level?`Nivel ${num(p.level)}`:'En caja'}</p></div></div>`}
function card(p,i){if(!p)return `<strong>0${i+1}</strong><p>Sin Pokémon</p>`;const ratio=Number(p.hp)/Number(p.max_hp)*100,hp=Number.isFinite(ratio)?Math.max(0,Math.min(100,ratio)):0;return `<div class="card-top"><span>EQUIPO / 0${i+1}</span><span>${p.hp===0?'DEBILITADO':`NIVEL ${num(p.level)}`}</span></div>${portrait(p)}<div class="hp-label"><span>PS</span><span>${num(p.hp)} / ${num(p.max_hp)}</span></div><div class="hp-track"><span style="width:${hp}%"></span></div><div class="stats">${labels.map(([key,name])=>`<div class="stat"><small>${name}</small><strong>${num(p.stats?.[key])}</strong></div>`).join('')}</div><div class="traits"><div><span>Habilidad</span>${esc(p.ability)}</div><div><span>Objeto</span>${itemIcon(p)}${esc(p.item)}</div><div><span>Origen</span>${esc(p.met_location||'Sin lugar registrado')}</div></div><div class="moves">${list(p.move_names).map(m=>`<div class="move">${esc(m)}</div>`).join('')}</div>`}
// Held item icon served by the local tracker (custom icons included); spriteFallback hides it on 404.
// Partner snapshots get none: their item ids may be missing or belong to another game.
function itemIcon(p){
  const id=p?.item_id;
  if((typeof companionView!=='undefined'&&companionView)||typeof id!=='number'||!Number.isInteger(id)||id<1)return '';
  return `<img class="item-icon" src="/overlay/item/${num(id)}.png" data-item-icon="" alt="" width="24" height="24" loading="lazy">`;
}
// Party cards repaint only when their Pokémon changes.
function renderPartyCards(snapshot){
  nodes.forEach((node,i)=>{
    const p=snapshot.party[i],sig=JSON.stringify(p)+(companionView?'|compañero':'');
    node.setAttribute('aria-label',p?'Abrir ficha de '+(p.nickname||p.species):'Espacio '+(i+1)+' vacío');
    node.setAttribute('aria-disabled',String(!p));
    node.tabIndex=p?0:-1;
    if(node.dataset.signature===sig)return;
    node.dataset.signature=sig;
    node.classList.toggle('empty',!p);
    node.innerHTML=card(p,i);
  });
}
function renderMini(){
  if($('death-counter-value'))$('death-counter-value').textContent=String(state.progress?.death_count??Object.keys(state.progress?.deaths||{}).length);
  const signature=JSON.stringify(state.party.map(p=>p?[p.species_id,p.nickname,p.hp===0]:null));
  $('party-count').textContent=state.party.filter(Boolean).length;
  $('box-count').textContent=Object.keys(state.boxes).length;
  if(signature===miniSignature)return;
  miniSignature=signature;
  $('mini-team').replaceChildren();
  state.party.forEach((p,i)=>$('mini-team').append(miniTeamButton(p,i)));
}
// Top-bar button for one party slot; it opens the same detail as the large card.
function miniTeamButton(p,i){
  const b=document.createElement('button');
  b.title=p?`${p.nickname||p.species} · ${p.species}`:`Espacio ${i+1} vacío`;
  if(!p)b.setAttribute('aria-label','Espacio vacío');
  b.className=p?.hp===0?'fainted':'';
  b.innerHTML=p
    ?`<img src="/sprites/${spriteId(p.species_id)}.png" data-fallback="${spriteId(p.species_id)}" alt="${esc(p.species)}" loading="lazy"><span hidden>${i+1}</span>`
    :`<span aria-hidden="true">·</span>`;
  b.onclick=()=>{switchTab('party');if(p)openDetail(state.party[i],`party:${i}`)};
  return b;
}
