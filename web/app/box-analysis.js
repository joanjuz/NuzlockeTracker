'use strict';
// Boxes · analysis view: a read-only table of the stored Pokémon with base stats, filters and sorting.
// It never sends a command: nothing here moves a Pokémon or touches the game.
const BOX_ANALYSIS_LIMIT=240;
const BOX_BASE_STATS=[['HP','PS'],['ATK','Ataque'],['DEF','Defensa'],['SPA','At. esp.'],['SPD','Def. esp.'],['SPE','Velocidad']];
const BOX_CURRENT_STATS={ATK:'ATQ',DEF:'DEF',SPA:'ATE',SPD:'DEE',SPE:'VEL'};
let boxAnalysisSignature='',boxAnalysisFacets='';
function boxAnalysisMode(){return $('box-view-mode').value==='analysis'}
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
  const p=entry.pokemon,id=spriteId(p.species_id);
  const badges=(entry.dead?'<span class="box-badge">Muerto</span>':'')+(entry.egg?'<span class="box-badge">Huevo</span>':'');
  const moves=list(p.move_names).filter(name=>name&&name!=='—').map(name=>`<span>${esc(name)}</span>`).join('')||'—';
  const place=entry.kind==='party'?`Equipo · ${entry.slot+1}`:`Caja ${num(entry.box)} · ${entry.slot+1}`;
  return `<tr class="${entry.dead?'box-row-dead':''}">`
    +`<th scope="row"><button type="button" class="box-analysis-open" data-entry="${esc(entry.key)}" aria-label="Abrir ficha de ${esc(TeamInsights.label(p))}">`
    +`<img src="/sprites/${id}.png" data-fallback="${id}" alt="" width="44" height="44" loading="lazy">`
    +`<span><strong>${esc(TeamInsights.label(p))}</strong><small>${esc(p.species)}</small>${badges}</span></button></th>`
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
  const gen6=GEN6_GAMES.includes(state.game),total=gen6?31:32,read=Object.keys(state.boxes||{}).length;
  const notes=[`${shown} Pokémon`,`${read} / ${total} cajas leídas`];
  if(read<total)notes.push('faltan cajas por leer: el resultado es parcial');
  if(state.scan?.active)notes.push('lectura en curso');
  if(state.box_verified===false)notes.push('cajas no verificadas en esta conexión');
  if(companionView)notes.push('cajas del compañero (último registro)');
  else if(state.stale)notes.push('última lectura guardada');
  if(entries.length&&!entries.some(entry=>TeamInsights.bst(entry.pokemon)!==null))
    notes.push('sin estadísticas base: importa Definitive Game Data o el CSV de estadísticas para ver BST');
  return notes.join(' · ');
}
function renderBoxAnalysis(){
  if(!state)return;
  const all=$('global').checked||$('living-dex').checked;
  const entries=TeamInsights.ownedEntries(state,{party:$('box-analysis-party').checked,boxes:true});
  syncBoxAnalysisFacets(entries);
  const filters={type:$('box-analysis-type').value,ability:$('box-analysis-ability').value,available:$('box-analysis-available').checked,
    query:$('search').value,box:all?0:Number($('box').value)};
  const sort=$('box-analysis-sort').value||'bst',direction=$('box-analysis-direction').value==='asc'?'asc':'desc';
  // Only what the table draws: full PK6/PK7 records are not serialised on every frame.
  const signature=JSON.stringify([state.game,companionView,state.stale,state.box_verified,state.scan?.active,Object.keys(state.boxes||{}).length,filters,sort,direction,
    entries.map(e=>[e.key,e.id,e.dead,e.egg,e.pokemon.species,e.pokemon.nickname,e.pokemon.level,e.pokemon.max_hp,e.pokemon.ability,e.pokemon.nature,
      e.pokemon.types,e.pokemon.base_stats,e.pokemon.stats,e.pokemon.move_names])]);
  if(signature===boxAnalysisSignature)return;
  boxAnalysisSignature=signature;
  const found=TeamInsights.sortEntries(TeamInsights.filterEntries(entries,filters),sort,direction);
  setText($('box-analysis-status'),boxAnalysisStatus(entries,found.length));
  $('box-analysis').innerHTML=found.length?boxAnalysisTable(found.slice(0,BOX_ANALYSIS_LIMIT),found.length)
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
for(const id of ['box-analysis-type','box-analysis-ability','box-analysis-direction','box-analysis-available','box-analysis-party'])$(id).onchange=renderBoxes;
$('box-analysis-sort').onchange=()=>{
  // Names and types read naturally A→Z; numbers start from the highest.
  $('box-analysis-direction').value=['name','type'].includes($('box-analysis-sort').value)?'asc':'desc';
  renderBoxes();
};
