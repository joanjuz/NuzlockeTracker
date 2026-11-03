'use strict';
// Pokémon detail dialog and move sheet.
function openDetail(p,key){if(!p)return;selected=key;detailSignature='';detail(p);if(!$('detail').open)$('detail').showModal()}
function wikidexUrl(name){return 'https://www.wikidex.net/wiki/'+encodeURIComponent(String(name||'').trim().replace(/\s+/g,'_'))}
function wikiPokemonName(p){return Number(p.form)===1&&[20,26,27,28,37,38,50,51,52,53,74,75,76,88,89,103,105].includes(Number(p.species_id))?p.species+' de Alola':p.species}
function detail(p){
detailPokemon=p;
const signature=JSON.stringify(p);
if(signature===detailSignature)return;
detailSignature=signature;
const content=$('detail-content'),active=document.activeElement;
const focusedMove=content.contains(active)?active?.getAttribute('data-move-index'):null;
content.innerHTML=portrait(p)
  +`<p class="subtitle">${esc(p.nature)} · ${esc(p.ability)} · ${itemIcon(p)}${esc(p.item)}</p>`
  +detailMoves(p)
  +detailBaseStats(p)
  +detailEvolutions(p)
  +detailOrigin(p)
  +detailTraining(p);
const title=content.querySelector('h2');if(title)title.id='detail-pokemon-title';
if(focusedMove!==null&&$('detail').open){
  const replacement=content.querySelector('[data-move-index="'+focusedMove+'"]');
  if(replacement&&!replacement.disabled)replacement.focus({preventScroll:true});
}
}
// Pieces of the detail dialog. Every snapshot value goes through esc/num/list.
function detailMoves(p){
  const buttons=list(p.move_names).map((m,i)=>
    `<button class="move move-button" data-move-index="${i}" ${list(p.moves)[i]?'':'disabled'}>${esc(m)} <span>↗</span></button>`
  );
  return `<div class="moves">${buttons.join('')}</div>`;
}
function detailBaseStats(p){
  if(!(p.base_stats&&typeof p.base_stats==='object'))return '';
  const cells=Object.entries(p.base_stats).map(([key,val])=>
    `<div><small>${esc(key)}</small><strong>${esc(val)}</strong></div>`
  );
  return '<section class="template-base-stats">'
    +'<h3>Estadísticas base · pk3DS Progressive</h3>'
    +`<div class="template-base-grid">${cells.join('')}</div>`
    +'<p class="subtitle">Los valores actuales de la partida y los IV/EV se muestran por separado.</p>'
    +'</section>';
}
function evolutionOption(e){
  const sourceNote=e.source==='pk3DS Progressive'
    ?'<small class="evolution-modified">Método modificado por pk3DS Progressive</small>'
    :'<small class="reference-note">Referencia de evolución</small>';
  return '<div class="evolution-option">'
    +`<img src="/sprites/${spriteId(e?.sprite_id||e?.target)}.png" data-fallback="${spriteId(e?.sprite_id||e?.target)}" alt="${esc(e?.target_name||'Pokémon '+e?.target)}" loading="lazy">`
    +`<span class="sprite-fallback" hidden>#${num(e?.target)}</span>`
    +'<div>'
    +'<div class="evolution-pokemon-title">'
    +`<strong>${esc(e.target_name||'#'+e.target)}</strong>`
    +`<a class="evolution-wiki" href="${esc(wikidexUrl(e.target_name||'Pokémon '+e.target))}" target="_blank" rel="noopener noreferrer" aria-label="Ver ${esc(e.target_name||'Pokémon '+e.target)} en WikiDex">WikiDex ↗</a>`
    +'</div>'
    +`<p>${esc(e.method)}</p>`
    +sourceNote
    +'</div>'
    +'</div>';
}
function detailEvolutions(p){
  if(!list(p.evolutions).some(e=>e&&typeof e==='object'))return '';
  const options=list(p.evolutions).filter(e=>e&&typeof e==='object').map(e=>evolutionOption(e));
  return '<section class="evolution-info">'
    +'<div class="evolution-heading">'
    +'<h3>Cómo evoluciona</h3>'
    +`<a class="evolution-wiki" href="${esc(wikidexUrl(wikiPokemonName(p)))}" target="_blank" rel="noopener noreferrer" aria-label="Consultar ${esc(wikiPokemonName(p))} en WikiDex">WikiDex ↗</a>`
    +'</div>'
    +options.join('')
    +'</section>';
}
function detailOrigin(p){
  const egg=p.egg_location_id?`<br>Origen del huevo: ${esc(p.egg_location)}`:'';
  return '<div class="origin-info">'
    +'<strong>Lugar registrado</strong>'
    +`<p>${esc(p.met_location||'Sin lugar registrado')}</p>`
    +`<small>Nivel de encuentro: ${p.met_level?num(p.met_level):'—'} · Fecha: ${esc(p.met_date)}${egg}</small>`
    +'</div>';
}
function detailTraining(p){
  // IV/EV arrays use the game order: PS, Ataque, Defensa, Velocidad, At. esp., Def. esp.
  const rows=[['PS',0],['Ataque',1],['Defensa',2],['At. especial',4],['Def. especial',5],['Velocidad',3]].map(([name,i])=>
    `<tr><td>${name}</td><td>${num(list(p.iv)[i])}</td><td>${num(list(p.ev)[i])}</td></tr>`
  );
  return '<h3>Valores individuales y esfuerzo</h3>'
    +'<table class="detail-stats">'
    +'<thead><tr><th>Estadística</th><th>IV</th><th>EV</th></tr></thead>'
    +`<tbody>${rows.join('')}</tbody>`
    +'</table>';
}
// Keeps an open detail dialog in sync with the snapshot, or closes it if the Pokémon is gone.
function refreshOpenDetail(snapshot){
  if(!(selected&&$('detail').open))return;
  const [kind,a,b]=selected.split(':');
  const p=kind==='dead'?snapshot.progress?.deaths?.[`${a}:${b}`]?.pokemon:kind==='party'?snapshot.party[a]:snapshot.boxes[a]?.[b];
  if(p)detail(p);
  else $('detail').close();
}
$('close-detail').onclick=()=>$('detail').close();
$('detail-content').addEventListener('click',event=>{const button=event.target.closest('[data-move-index]');if(button&&detailPokemon)openMove(detailPokemon,Number(button.dataset.moveIndex))});
async function openMove(p,index){
  const id=Number(list(p.moves)[index]);
  if(!Number.isInteger(id)||id<1)return;
  const request=++moveRequest;
  $('move-content').innerHTML='<h2 id="move-title">Movimiento</h2><p class="subtitle">Cargando ficha…</p>';
  if(!$('move-detail').open)$('move-detail').showModal();
  try{
    const response=await fetch(`/api/move/${id}`);
    const m=await response.json();
    if(!response.ok)throw Error(m.error||'No se pudo cargar el movimiento.');
    if(request!==moveRequest)return;
    $('move-content').innerHTML=moveSheet(m,id,list(p.move_pp)[index],list(p.move_pp_ups)[index]);
  }catch(e){
    if(request===moveRequest)$('move-content').innerHTML=`<h2 id="move-title">Movimiento</h2><p>${esc(e.message)}</p>`;
  }
}
// Move dialog body: reference data from /api/move plus the live PP of this Pokémon.
function moveSheet(m,id,current,ups){
  const maximum=Number.isInteger(ups)&&ups>=0&&ups<=3?Math.floor(m.pp*(5+ups)/5):null;
  const typeClass=normalize(m.type).replace(/[^a-z]/g,'');
  const power=m.power!=null?num(m.power):(m.category==='Estado'?'—':'Variable');
  const livePp=current!=null
    ?`<p class="live-pp">PP actuales: <strong>${num(current)}</strong>${maximum!=null?` · Máximo: ${num(maximum)}`:''}</p>`
    :'';
  const notes=esc(m.source)
    +(m.rom_override?'':' · Puede variar con el randomizer.')
    +(m.template_notes?` · ${esc(m.template_notes)}`:'')
    +(m.battle_patch?' · Efecto especial requiere parche validado en la ROM.':'');
  return `<p class="eyebrow">MOVIMIENTO / ${num(id)}</p>`
    +`<h2 id="move-title">${esc(m.name)}</h2>`
    +`<div class="move-tags"><span class="type-tag type-${typeClass}">${esc(m.type)}</span><span>${esc(m.category)}</span></div>`
    +'<div class="move-facts">'
    +`<div><small>Potencia</small><strong>${power}</strong></div>`
    +`<div><small>Precisión</small><strong>${m.accuracy==null?'—':num(m.accuracy)+'%'}</strong></div>`
    +`<div><small>PP base</small><strong>${num(m.pp)}</strong></div>`
    +`<div><small>Prioridad</small><strong>${m.priority>0?'+':''}${num(m.priority)}</strong></div>`
    +'</div>'
    +livePp
    +`<p class="move-description">${esc(m.description)}</p>`
    +`<p class="reference-note">${notes}</p>`
    +`<a class="wiki-link" href="${esc(m.wikidex_url)}" target="_blank" rel="noopener noreferrer">WikiDex ↗</a>`;
}
$('close-move').onclick=()=>{moveRequest++;$('move-detail').close()};$('move-detail').addEventListener('close',()=>moveRequest++);
// Dismiss native dialogs on backdrop click; clicks inside their bounds stay open.
for(const id of ['detail','move-detail'])$(id).addEventListener('click',event=>{if(event.target!==$(id))return;const r=$(id).getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)$(id).close()});
