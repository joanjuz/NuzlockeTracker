'use strict';
// Boxes · analysis view: a gallery first, with an optional reference table.
// It never sends a command: nothing here moves a Pokémon or touches the game.
const BOX_ANALYSIS_LIMIT=240;
const BOX_BASE_STATS=[['HP','PS'],['ATK','Ataque'],['DEF','Defensa'],['SPA','At. esp.'],['SPD','Def. esp.'],['SPE','Velocidad']];
const BOX_CURRENT_STATS={ATK:'ATQ',DEF:'DEF',SPA:'ATE',SPD:'DEE',SPE:'VEL'};
let boxAnalysisSignature='',boxAnalysisFacets='';
function boxAnalysisMode(){return $('box-view-mode').value==='analysis'}
function boxAnalysisPresentation(){return $('box-analysis-presentation')?.value==='table'?'table':'cards'}
function boxAnalysisPokemon(p){return typeof analysisPokemon==='function'?analysisPokemon(p):p}
function boxAnalysisPlace(entry){return entry.kind==='party'?`Equipo · ${entry.slot+1}`:`Caja ${num(entry.box)} · ${entry.slot+1}`}
function boxAnalysisMega(entry){return typeof analysisMegaControl==='function'?analysisMegaControl(entry.sourcePokemon||entry.pokemon):''}
function boxAnalysisSource(p){
  if(!BOX_BASE_STATS.some(([key])=>TeamInsights.baseStat(p,key)!==null))return '';
  const source=String(p.base_stats_source||'Procedencia no indicada');
  const short=/Definitive|DGD/.test(source)?'Datos de la partida':/pk3DS|CSV/.test(source)?'CSV importado':/Referencia|PKHeX/.test(source)?'Referencia local':'Bases de especie';
  return `<span class="box-card-source" title="${esc(source)}">${short}</span>`;
}
function boxAnalysisStats(p){
  const labels={HP:'PS',ATK:'Atq',DEF:'Def',SPA:'At. E',SPD:'Def. E',SPE:'Vel'};
  const known=BOX_BASE_STATS.map(([key])=>TeamInsights.baseStat(p,key));
  const best=Math.max(...known.filter(value=>value!==null));
  const rows=BOX_BASE_STATS.map(([key,name],index)=>{
    const value=known[index],width=value===null?0:Math.max(0,Math.min(100,value/255*100));
    return `<div class="box-base-stat${value!==null&&value===best?' box-base-stat-best':''}"><dt title="${name}">${labels[key]}</dt>`
      +`<dd><span class="box-base-track" aria-hidden="true"><i style="width:${width.toFixed(2)}%"></i></span><span>${value===null?'—':num(value)}</span></dd></div>`;
  }).join('');
  return `<dl class="box-base-stats" aria-label="Estadísticas base de la especie">${rows}</dl>`
    +(known.every(value=>value===null)?'<p class="box-card-unavailable">Bases no disponibles para esta forma.</p>':'');
}
function boxAnalysisCurrent(p){
  const actual=BOX_BASE_STATS.map(([key,name])=>{const value=boxCurrentStat(p,key);return value===null?'':`<div><dt>${name}</dt><dd>${num(value)}</dd></div>`}).filter(Boolean);
  return actual.length?'<details class="box-current-values"><summary>Estadísticas actuales</summary><p>Valores del ejemplar leído; no son las bases de la especie.</p><dl>'+actual.join('')+'</dl></details>':'';
}
function boxAnalysisCard(entry){
  const p=entry.pokemon,id=spriteId(p.sprite_id||p.species_id),total=TeamInsights.bst(p);
  const mega=boxAnalysisMega(entry);
  const tags=[entry.dead?'Muerto':'',entry.egg?'Huevo':'',p.analysis_mega?String(p.analysis_preview_label||'Mega simulada'):''].filter(Boolean);
  const moves=list(p.move_names).filter(name=>name&&name!=='—').slice(0,4);
  return `<article class="box-analysis-card${entry.dead?' box-card-dead':''}">`
    +'<div class="box-card-heading">'
    +`<button type="button" class="box-card-open" data-entry="${esc(entry.key)}" aria-label="Abrir ficha de ${esc(TeamInsights.label(p))}">`
    +`<img src="/sprites/${id}.png" data-fallback="${id}" alt="" width="80" height="80" loading="lazy">`
    +`<span class="box-card-identity"><strong class="box-card-name">${esc(TeamInsights.label(p))}</strong><small>${esc(p.species)}</small>`
    +`<span class="box-card-types">${list(p.types).map(type=>`<span>${esc(type)}</span>`).join('')}</span></span></button>`
    +`<span class="box-card-bst"><b>${total===null?'—':num(total)}</b><small>BST</small></span></div>`
    +(tags.length?`<div class="box-card-tags">${tags.map(tag=>`<span>${esc(tag)}</span>`).join('')}</div>`:'')
    +'<div class="box-card-facts">'
    +`<div><span>Habilidad</span><b>${esc(p.ability)}</b></div><div><span>Naturaleza</span><b>${esc(p.nature)}</b></div></div>`
    +boxAnalysisStats(p)
    +`<div class="box-card-moves" aria-label="Movimientos conocidos">${moves.length?moves.map(move=>`<span>${esc(move)}</span>`).join(''):'<span class="box-card-unavailable">Movimientos sin leer</span>'}</div>`
    +boxAnalysisCurrent(p)
    +'<footer class="box-card-footer">'
    +`<span>${boxAnalysisPlace(entry)}${Number.isInteger(p.level)?`<small>Nivel ${num(p.level)}</small>`:'<small>Nivel sin leer</small>'}</span>`
    +boxAnalysisSource(p)+'</footer>'
    +(mega?`<div class="box-card-mega">${mega}</div>`:'')
    +'</article>';
}
function boxAnalysisGallery(entries,total){
  return `<div class="box-analysis-gallery">${entries.map(boxAnalysisCard).join('')}</div>`
    +(total>entries.length?`<p class="subtitle box-analysis-more">Se muestran ${entries.length} de ${total}. Afina los filtros para ver el resto.</p>`:'');
}
// Current value of the specimen (party only); boxes have no calculated stats.
function boxCurrentStat(p,key){
  const value=key==='HP'?p.max_hp:p.stats&&typeof p.stats==='object'?p.stats[BOX_CURRENT_STATS[key]]:null;
  return typeof value==='number'&&Number.isFinite(value)?value:null;
}
function boxAnalysisStatCells(p){
  const base=BOX_BASE_STATS.map(([key])=>TeamInsights.baseStat(p,key));
  const current=key=>{const value=boxCurrentStat(p,key);return value===null?'':`<small class="box-current-stat">actual ${num(value)}</small>`};
  if(base.every(value=>value===null)){
    const actual=BOX_BASE_STATS.map(([key,name])=>{const value=boxCurrentStat(p,key);return value===null?'':`${name} ${num(value)}`}).filter(Boolean).join(' · ');
    return `<td colspan="7" class="box-stat-missing">Estadísticas base: No disponible${actual?`<small class="box-current-stat">actual · ${actual}</small>`:''}</td>`;
  }
  const total=TeamInsights.bst(p);
  return BOX_BASE_STATS.map(([key],i)=>`<td>${base[i]===null?'<span class="box-stat-missing">No disponible</span>':num(base[i])}${current(key)}</td>`).join('')
    +`<td class="box-bst">${total===null?'<span class="box-stat-missing">No disponible</span>':num(total)}</td>`;
}
function boxAnalysisRow(entry){
  const p=entry.pokemon,id=spriteId(p.sprite_id||p.species_id);
  const badges=(entry.dead?'<span class="box-badge">Muerto</span>':'')+(entry.egg?'<span class="box-badge">Huevo</span>':'');
  const moves=list(p.move_names).filter(name=>name&&name!=='—').map(name=>`<span>${esc(name)}</span>`).join('')||'—';
  const place=boxAnalysisPlace(entry);
  return `<tr class="${entry.dead?'box-row-dead':''}">`
    +`<th scope="row"><button type="button" class="box-analysis-open" data-entry="${esc(entry.key)}" aria-label="Abrir ficha de ${esc(TeamInsights.label(p))}">`
    +`<img src="/sprites/${id}.png" data-fallback="${id}" alt="" width="44" height="44" loading="lazy">`
    +`<span><strong>${esc(TeamInsights.label(p))}</strong><small>${esc(p.species)}</small>${badges}</span></button>${boxAnalysisMega(entry)}</th>`
    +`<td>${Number.isInteger(p.level)?num(p.level):'<span class="box-stat-missing">No disponible</span>'}</td>`
    +`<td>${list(p.types).map(type=>esc(type)).join(' / ')||'—'}</td>`
    +`<td>${esc(p.ability)}</td><td>${esc(p.nature)}</td>`
    +boxAnalysisStatCells(p)
    +`<td class="box-moves">${moves}</td><td>${place}</td></tr>`;
}
function boxAnalysisTable(entries,total){
  const head=['Pokémon','Nivel','Tipos','Habilidad','Naturaleza',...BOX_BASE_STATS.map(([,name])=>name+' base'),'BST','Movimientos','Ubicación'];
  const more=total>entries.length?`<p class="subtitle">Se muestran ${entries.length} de ${total}. Afina los filtros para ver el resto.</p>`:'';
  return '<div class="analysis-scroll"><table class="analysis-table box-analysis-table">'
    +'<caption>Las columnas «base» son estadísticas de la especie y BST es su suma. «actual» es el valor del ejemplar en la partida y solo se conoce en el equipo.</caption>'
    +`<thead><tr>${head.map(name=>`<th scope="col">${name}</th>`).join('')}</tr></thead>`
    +`<tbody>${entries.map(boxAnalysisRow).join('')}</tbody></table></div>${more}`;
}
// Type and ability options follow the Pokémon that exist; the current choice is kept.
function syncBoxAnalysisFacets(entries){
  const facets=TeamInsights.entryFacets(entries),signature=JSON.stringify(facets);
  if(signature===boxAnalysisFacets)return;
  boxAnalysisFacets=signature;
  for(const [id,values,all] of [['box-analysis-type',facets.types,'Todos los tipos'],['box-analysis-ability',facets.abilities,'Todas las habilidades']]){
    const before=$(id).value;
    $(id).replaceChildren();
    $(id).add(new Option(all,''));
    for(const value of values)$(id).add(new Option(value,value));
    $(id).value=values.includes(before)?before:'';
  }
}
function boxAnalysisStatus(entries,shown){
  const gen6=GEN6_GAMES.includes(state.game),total=gen6?31:32;
  const read=Array.from({length:total},(_,i)=>state.boxes?.[String(i+1)]).filter(box=>Array.isArray(box)&&box.length===30).length;
  const notes=[`${shown} Pokémon`,`${read} / ${total} cajas leídas`];
  if(read<total)notes.push('faltan cajas por leer: el resultado es parcial');
  if(state.scan?.active)notes.push('lectura en curso');
  if(state.box_verified===false)notes.push('cajas no verificadas en esta conexión');
  if(companionView)notes.push('cajas del compañero (último registro)');
  else if(state.stale)notes.push('última lectura guardada');
  if(entries.length&&!entries.some(entry=>TeamInsights.bst(entry.pokemon)!==null))
    notes.push('sin estadísticas base para las formas disponibles');
  return notes.join(' · ');
}
function renderBoxAnalysis(){
  if(!state)return;
  const all=$('global').checked||$('living-dex').checked;
  const entries=TeamInsights.ownedEntries(state,{party:$('box-analysis-party').checked,boxes:true})
    .map(entry=>({...entry,sourcePokemon:entry.pokemon,pokemon:boxAnalysisPokemon(entry.pokemon)}));
  syncBoxAnalysisFacets(entries);
  const filters={type:$('box-analysis-type').value,ability:$('box-analysis-ability').value,available:$('box-analysis-available').checked,
    query:$('search').value,box:all?0:Number($('box').value)};
  const sort=$('box-analysis-sort').value||'bst',direction=$('box-analysis-direction').value==='asc'?'asc':'desc',presentation=boxAnalysisPresentation();
  // Only what the table draws: full PK6/PK7 records are not serialised on every frame.
  const signature=JSON.stringify([state.game,companionView,state.stale,state.box_verified,state.scan?.active,Object.values(state.boxes||{}).map(box=>Array.isArray(box)?box.length:0),filters,sort,direction,presentation,
    entries.map(e=>[e.key,e.id,e.dead,e.egg,e.pokemon.species,e.pokemon.nickname,e.pokemon.level,e.pokemon.max_hp,e.pokemon.ability,e.pokemon.nature,
      e.pokemon.types,e.pokemon.base_stats,e.pokemon.base_stats_source,e.pokemon.stats,e.pokemon.move_names,e.pokemon.item,e.pokemon.met_location,e.pokemon.sprite_id,e.pokemon.analysis_mega,e.pokemon.analysis_preview_label,e.sourcePokemon.mega_preview])]);
  if(signature===boxAnalysisSignature)return;
  boxAnalysisSignature=signature;
  const found=TeamInsights.sortEntries(TeamInsights.filterEntries(entries,filters),sort,direction);
  setText($('box-analysis-status'),boxAnalysisStatus(entries,found.length));
  $('box-analysis').innerHTML=found.length?(presentation==='table'?boxAnalysisTable:boxAnalysisGallery)(found.slice(0,BOX_ANALYSIS_LIMIT),found.length)
    :`<p class="subtitle">${entries.length?'Ningún Pokémon coincide con los filtros.':'No hay Pokémon en las cajas leídas.'}</p>`;
}
function boxAnalysisEntry(key){
  const [kind,a,b]=String(key).split(':');
  return kind==='party'?state?.party?.[a]:kind==='box'?state?.boxes?.[a]?.[b]:null;
}
$('box-analysis').addEventListener('click',event=>{
  const button=event.target.closest('[data-entry]');
  if(button)openDetail(boxAnalysisEntry(button.dataset.entry),button.dataset.entry);
});
function switchBoxViewMode(){
  const analysis=boxAnalysisMode();
  // Living Dex belongs to the normal view; its choice is kept for when the user comes back.
  $('living-dex-label').hidden=$('living-dex-sprites-label').hidden=analysis;
  boxAnalysisSignature='';boxSignature='';
  renderBoxes();
}
$('box-view-mode').onchange=switchBoxViewMode;
for(const id of ['box-analysis-type','box-analysis-ability','box-analysis-direction','box-analysis-available','box-analysis-party','box-analysis-presentation'])if($(id))$(id).onchange=renderBoxes;
$('box-analysis-sort').onchange=()=>{
  // Names and types read naturally A→Z; numbers start from the highest.
  $('box-analysis-direction').value=['name','type'].includes($('box-analysis-sort').value)?'asc':'desc';
  renderBoxes();
};
