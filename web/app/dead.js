'use strict';
// Dead Pokémon list and the shared route/box sprite.
function pokemonKey(p){return `${p.origin_version??33}:${p.encryption_constant}`}
function isDead(p){return Boolean(state?.progress?.deaths?.[pokemonKey(p)])}
function renderDead(){
 const deaths=state.progress?.deaths||{},signature=JSON.stringify(deaths);
 $('dead-count').textContent=Object.keys(deaths).length;
 if(signature===deadSignature)return;deadSignature=signature;$('dead').replaceChildren();
 for(const [key,record] of Object.entries(deaths)){
  const p=record?.pokemon;if(!p||typeof p!=='object')continue;
  const entry=document.createElement('article'),detailButton=document.createElement('button'),reviveButton=document.createElement('button');
  entry.className='dead-entry';detailButton.className='box-pokemon';
  detailButton.innerHTML=`${sprite(p)}<strong>${esc(p.nickname||p.species)}</strong><small>${esc(p.met_location||'Origen desconocido')}</small>`;
  detailButton.onclick=()=>openDetail(p,`dead:${key}`);
  reviveButton.className='revive-button';reviveButton.textContent='Revivir';reviveButton.setAttribute('aria-label',`Revivir a ${p.nickname||p.species}`);
  reviveButton.title='Quitar de Muertos. No cambia los PS del juego.';
  reviveButton.disabled=typeof companionView!=='undefined'&&companionView;
  reviveButton.onclick=async()=>{
   reviveButton.disabled=true;
   try{
    const lower=confirm('¿Quieres reducir también el contador de muertes en 1?');
    await command({action:'revive',key,decrement_counter:lower});
   }finally{
    reviveButton.disabled=false;
   }
  };
  entry.append(detailButton,reviveButton);$('dead').append(entry);
 }
 if(!Object.keys(deaths).length)$('dead').innerHTML='<p class="subtitle">Sin muertes registradas.</p>';
}
function sprite(p){
 const dead=isDead(p),id=spriteId(p.species_id);
 return `<div class="route-sprite ${dead?'dead-sprite':''}" title="${dead?'Muerto · ':''}${esc(p.nickname||p.species)} · ${esc(p.species)}">`
  +`<img src="/sprites/${id}.png" data-fallback="${id}" alt="${esc(p.species)}" loading="lazy">`
  +`<span class="sprite-number" hidden>#${num(p.species_id)}</span></div>`;
}
