'use strict';
// Team assistant: virtual teams built from the Pokémon the user owns (party and read boxes).
// Purely informative: it never sends a command and never changes the party in the game.
const BUILDER_CANDIDATE_LIMIT=120;
let analysisSection='current',builderMembers=[],builderContext='',builderSignature='',builderTypes='';
let builderPickerSlot=null,builderPickerLimit=6,builderPickerScope='';
const builderPokemon=p=>typeof analysisPokemon==='function'?analysisPokemon(p):p;
function builderEntries(){return TeamInsights.candidateEntries(state).map(entry=>({...entry,originalPokemon:entry.pokemon,pokemon:builderPokemon(entry.pokemon)}))}
const builderMegaControl=p=>typeof analysisMegaControl==='function'?analysisMegaControl(p):'';
const builderTypeChips=types=>list(types).map(type=>`<span class="builder-type-chip">${esc(type)}</span>`).join('');
function teamBuilderActive(){return analysisSection==='builder'}
function setAnalysisSection(section){
  analysisSection=section==='builder'?'builder':'current';
  if(analysisSection!=='builder')builderClosePicker();
  $('analysis-section-current').setAttribute('aria-pressed',String(analysisSection==='current'));
  $('analysis-section-builder').setAttribute('aria-pressed',String(analysisSection==='builder'));
  $('analysis-current').hidden=analysisSection!=='current';
  $('team-builder').hidden=analysisSection!=='builder';
  analysisSignature='';builderSignature='';
  // Reopening the assistant refreshes the saved list (the first load happens with the scope).
  if(state&&analysisSection==='builder'&&builderContext===builderScope())loadBuilderTeams();
  renderAnalysis();
}
// A virtual team belongs to one game and one view (own run or partner): switching starts a new draft.
function builderScope(){return JSON.stringify([state.game,companionView])}
function builderPlace(entry){return entry.kind==='party'?`Equipo · ${entry.slot+1}`:`Caja ${num(entry.box)} · ${entry.slot+1}`}
function builderSprite(speciesId){
  const id=spriteId(speciesId);
  return `<img src="/sprites/${id}.png" data-fallback="${id}" alt="" width="56" height="56" loading="lazy">`;
}
function builderSlot(item,index,count){
  if(!item)return `<li class="builder-slot builder-slot-empty"><button type="button" data-builder-slot="${index}" data-focus="slot${index}" aria-label="Elegir Pokémon para el hueco ${index+1}"><span aria-hidden="true">+</span><strong>Elegir Pokémon</strong><small>Hueco ${index+1}</small></button></li>`;
  const {member,entry,status}=item,p=entry?.pokemon;
  const name=p?TeamInsights.label(p):member.nickname||member.species||'Pokémon';
  const note=status==='missing'?'<small class="builder-warning">No localizado en el equipo ni en las cajas leídas</small>'
    :status==='changed'?`<small class="builder-warning">Antes era ${esc(member.species)}</small>`:'';
  const tags=p?`<small>${esc(p.species)} · ${list(p.types).map(type=>esc(type)).join(' / ')||'—'}</small><small>${builderPlace(entry)}${entry.dead?' · muerto':''}${entry.historical?' · lectura guardada':''}</small>`
    :`<small>${esc(member.species)}</small>`;
  return `<li class="builder-slot${status==='missing'?' builder-slot-missing':''}">`
    +builderSprite(p?p.species_id:member.species_id)
    +`<div><strong>${esc(name)}</strong>${tags}${p?.analysis_mega?'<small class="builder-warning">'+esc(p.analysis_preview_label||'Mega simulada')+'</small>':''}${note}</div>`
    +'<div class="builder-slot-actions">'+(entry?builderMegaControl(entry.originalPokemon||p):'')
    +`<button type="button" data-builder-move="${index}:-1" data-focus="up${index}" aria-label="Subir a ${esc(name)}" ${index===0?'disabled':''}>↑</button>`
    +`<button type="button" data-builder-move="${index}:1" data-focus="down${index}" aria-label="Bajar a ${esc(name)}" ${index===count-1?'disabled':''}>↓</button>`
    +`<button type="button" data-builder-remove="${index}" data-focus="remove${index}" aria-label="Quitar a ${esc(name)} del equipo virtual">Quitar</button>`
    +'</div></li>';
}
function builderCandidate(entry,selected,full){
  const p=entry.pokemon,total=TeamInsights.bst(p);
  const hint=selected?'En el equipo virtual':full?'Equipo completo: quita o reemplaza un integrante':'Añadir al equipo virtual';
  return `<article class="builder-candidate-wrap"><button type="button" class="builder-candidate" data-builder-toggle="${esc(entry.id)}" data-focus="c${esc(entry.id)}" aria-pressed="${selected}" title="${hint}" ${full&&!selected?'disabled':''}>`
    +builderSprite(p.species_id)
    +`<strong>${esc(TeamInsights.label(p))}</strong>`
    +`<small>${list(p.types).map(type=>esc(type)).join(' / ')||'—'}</small>`
    +`<small>${builderPlace(entry)}${total===null?'':' · BST '+num(total)}</small>`
    +(entry.dead||entry.historical?`<small class="builder-warning">${[entry.dead?'Muerto':'',entry.historical?'Lectura guardada':''].filter(Boolean).join(' · ')}</small>`:'')
    +'</button>'+builderMegaControl(entry.originalPokemon||p)+'</article>';
}
function builderList(title,items,empty){
  return `<article class="builder-card"><h3>${title}</h3>${items.length?`<ul>${items.map(item=>`<li>${item}</li>`).join('')}</ul>`:`<p class="subtitle">${empty}</p>`}</article>`;
}
const builderNames=names=>names.map(name=>esc(name)).join(', ');
// Summary cards for a team; all facts come from TeamInsights.evaluateTeam.
function builderSummary(evaluation){
  const typesLine=types=>types.map(type=>esc(type)).join(', ');
  const weak=evaluation.sharedWeaknesses.map(w=>
    `<b>${esc(w.type)}</b>: ${w.weak} débiles (${builderNames(w.members)}) · ${w.answers.length?'lo resisten o son inmunes: '+builderNames(w.answers):'nadie lo resiste'}`);
  const immune=evaluation.immunities.map(i=>`<b>${esc(i.type)}</b>: ${builderNames(i.members)}`);
  const resist=evaluation.resistances.map(r=>`<b>${esc(r.type)}</b>: ${builderNames(r.members)}`);
  const redundancy=[
    ...evaluation.sharedTypes.map(s=>`${s.members.length} integrantes de tipo <b>${esc(s.type)}</b>: ${builderNames(s.members)}`),
    ...evaluation.attackTypes.filter(a=>a.count>=3).map(a=>`${a.count} ataques de tipo <b>${esc(a.type)}</b>: ${a.moves.map(m=>`${esc(m.name)} (${esc(m.pokemon)})`).join(', ')}`)
  ];
  const noMoves='No hay movimientos ofensivos conocidos en este equipo.';
  return '<div class="builder-cards">'
    +builderList('Debilidades compartidas',weak,'Ningún tipo es débil para dos o más integrantes.')
    +builderList('Tipos sin resistencia ni inmunidad',evaluation.unresisted.length?[typesLine(evaluation.unresisted)]:[],'Todos los tipos tienen al menos un integrante que los resiste.')
    +builderList('Resistencias',resist,'Ningún integrante resiste ningún tipo.')
    +builderList('Inmunidades',immune,'Ningún integrante es inmune a ningún tipo.')
    +builderList('Sin ataque supereficaz',evaluation.uncovered.length?[typesLine(evaluation.uncovered)]:[],evaluation.knownMoves?'Hay al menos un ataque supereficaz contra cada tipo.':noMoves)
    +builderList('Tipos que resisten todos tus ataques',evaluation.walled.length?[typesLine(evaluation.walled)]:[],evaluation.knownMoves?'Ningún tipo resiste todos los ataques conocidos.':noMoves)
    +builderList('Posibles redundancias',redundancy,'Sin tipos repetidos ni tres o más ataques del mismo tipo.')
    +'</div>';
}
function builderReport(team,abilities,entries){
  if(!team.length)return '<div class="builder-start"><h3>Elige tu primer integrante</h3><p class="subtitle">Pulsa un hueco o elige entre tus Pokémon disponibles.</p></div>';
  const types=analysisData.types,chart=analysisData.chart;
  const evaluation=TeamInsights.evaluateTeam(chart,types,team,abilities);
  return builderOverview(evaluation)
    +builderComparison(evaluation,abilities)
    +builderAdvice(evaluation,entries,abilities)
    +'<details class="builder-detail"><summary>Asesor de movimientos</summary>'+builderMoves(evaluation,abilities)+'</details>'
    +'<details class="builder-detail"><summary>Debilidades, resistencias y redundancias</summary>'+builderSummary(evaluation)+'</details>'
    +'<details class="builder-detail"><summary>Defensa por tipo</summary>'+defenseChart(team,types,chart,abilities,'weak')+'</details>'
    +'<details class="builder-detail"><summary>Cobertura ofensiva por tipo</summary>'+coverageReport(team,types,chart,abilities,false)+'</details>';
}
function builderOverview(evaluation){
  const weak=evaluation.sharedWeaknesses.slice(0,3).map(row=>row.type);
  const immunity=evaluation.immunities.length,covered=evaluation.knownMoves?evaluation.offense.length-evaluation.uncovered.length:null;
  return '<div class="builder-overview">'
    +`<div><h3>Vigila</h3><div class="builder-chip-row">${weak.length?builderTypeChips(weak):'<span>Sin debilidades compartidas</span>'}</div></div>`
    +`<div><h3>Falta cobertura</h3><div class="builder-chip-row">${!evaluation.knownMoves?'<span>Sin ataques conocidos</span>':evaluation.uncovered.length?builderTypeChips(evaluation.uncovered):'<span>Los 18 tipos cubiertos</span>'}</div></div>`
    +`<div><h3>Puntos fuertes</h3><p>${immunity} ${immunity===1?'tipo con inmunidad':'tipos con inmunidad'}${covered===null?'':` · ${covered} tipos cubiertos`}</p></div></div>`;
}
function builderComparison(virtual,abilities){
  const party=list(state.party).filter(p=>p&&!p.egg);
  const heading='<section class="builder-comparison" aria-label="Comparación con el equipo actual"><div class="builder-comparison-heading"><h3>Actual y virtual</h3><span>Comparación con el equipo actual</span></div>';
  if(!party.length)return heading+'<p class="subtitle">No hay un equipo actual leído para comparar.</p></section>';
  const current=TeamInsights.evaluateTeam(analysisData.chart,analysisData.types,party,abilities);
  const change=TeamInsights.compareTeams(current,virtual),before=TeamInsights.teamScores(current),after=TeamInsights.teamScores(virtual);
  const metric=(key,name,a,b,positive=true)=>{
    const delta=typeof a==='number'&&typeof b==='number'?b-a:null;
    const direction=delta===null||delta===0?'same':(delta>0)===positive?'gain':'risk';
    return `<div class="builder-compare-metric" data-metric="${key}"><span>${name}</span><div><b data-side="current">${a}</b><span class="builder-compare-arrow ${direction}" aria-label="${direction==='gain'?'Mejora':direction==='risk'?'Riesgo':'Sin cambio'}">→</span><b data-side="virtual">${b}</b></div></div>`;
  };
  const shortList=(items,kind,empty)=>items.length?items.slice(0,3).map(text=>`<span class="builder-effect ${kind}">${kind==='gain'?'+':'−'} ${esc(text)}</span>`).join(''):`<span class="builder-compare-empty">${empty}</span>`;
  return heading
    +'<div class="builder-compare-labels"><span>Actual</span><span>Virtual</span></div><div class="builder-compare-grid">'
    +metric('members','Integrantes localizados',current.size,virtual.size)
    +metric('defense','Balance defensivo',before.defense,after.defense)
    +metric('coverage','Tipos con ataque supereficaz',current.knownMoves?before.covered:'—',virtual.knownMoves?after.covered:'—')
    +metric('redundancy','Redundancias',before.redundancy,after.redundancy,false)
    +'</div><div class="builder-compare-effects">'
    +`<div><h4>Mejoras</h4>${shortList(change.gains,'gain','Sin nuevas coberturas ni resistencias.')}</div>`
    +`<div><h4>Riesgos</h4>${shortList(change.losses,'risk','Sin pérdidas de cobertura.')}</div></div>`
    +'<details class="builder-comparison-detail"><summary>Ver comparación completa</summary>'
    +`<p class="subtitle">${state.stale===true||state.connection?.status!=='connected'?'Comparación basada en lecturas guardadas. ':''}Solo cuentan los integrantes localizados; los ausentes conservan su hueco. El equipo del juego no cambia.</p>`
    +builderList('Qué aporta el equipo virtual',change.gains.map(text=>esc(text)),'Sin cambios de cobertura.')
    +builderList('Qué se pierde o empeora',change.losses.map(text=>esc(text)),'Sin pérdidas de cobertura.')
    +'</details></section>';
}
function syncBuilderTypes(entries){
  const types=TeamInsights.entryFacets(entries).types,signature=JSON.stringify(types);
  if(signature===builderTypes)return;
  builderTypes=signature;
  const before=$('builder-type').value;
  $('builder-type').replaceChildren();
  $('builder-type').add(new Option('Todos los tipos',''));
  for(const type of types)$('builder-type').add(new Option(type,type));
  $('builder-type').value=types.includes(before)?before:'';
}
function renderTeamBuilder(){
  if(!state||!analysisData)return;
  const scope=builderScope();
  if(scope!==builderContext){builderClosePicker();builderContext=scope;builderMembers=[];builderSignature='';builderOpenId=null;builderTeams=[];builderNotice='';$('builder-name').value='';loadBuilderTeams()}
  const entries=builderEntries();
  syncBuilderTypes(entries);
  const sort=$('builder-sort').value,abilities=$('builder-abilities').checked;
  const filters={query:$('builder-search').value,type:$('builder-type').value,kind:$('builder-source').value,hideDead:!$('builder-dead').checked,hideEggs:true};
  const signature=JSON.stringify([scope,builderMembers,builderOpenId,builderTeams,builderReadOnly,filters,sort,abilities,state.stale,state.connection?.status,state.box_verified,
    entries.map(e=>[e.id,e.key,e.dead,e.egg,e.historical,e.pokemon.species_id,e.pokemon.species,e.pokemon.nickname,e.pokemon.types,e.pokemon.ability_id,
      e.pokemon.base_stats,e.pokemon.analysis_moves,e.pokemon.level,e.pokemon.analysis_mega,e.pokemon.analysis_preview_label,e.pokemon.base_stats_source])]);
  if(signature===builderSignature)return;
  builderSignature=signature;
  const focused=document.activeElement?.dataset?.focus;
  const resolved=TeamInsights.resolveTeam(builderMembers,entries);
  const team=resolved.filter(item=>item.entry).map(item=>item.entry.pokemon);
  const missing=resolved.length-team.length;
  setText($('builder-count'),`${builderMembers.length} / ${TeamInsights.MAX_TEAM}`);
  $('builder-team').innerHTML=Array.from({length:TeamInsights.MAX_TEAM},(_,i)=>builderSlot(resolved[i],i,resolved.length)).join('');
  setText($('builder-status'),missing?`${missing} integrante${missing===1?'':'s'} no localizado${missing===1?'':'s'}: no se sustituye${missing===1?'':'n'} por otro Pokémon y no cuenta${missing===1?'':'n'} en la cobertura.`:'');
  const selected=new Set(builderMembers.map(member=>member.id)),full=builderMembers.length>=TeamInsights.MAX_TEAM;
  const found=TeamInsights.sortEntries(TeamInsights.filterEntries(entries,filters),sort,['name','type'].includes(sort)?'asc':'desc');
  setText($('builder-candidate-count'),`${found.length} de ${entries.length}`+(found.length>BUILDER_CANDIDATE_LIMIT?` · se muestran ${BUILDER_CANDIDATE_LIMIT}`:''));
  $('builder-candidates').innerHTML=found.length?found.slice(0,BUILDER_CANDIDATE_LIMIT).map(entry=>builderCandidate(entry,selected.has(entry.id),full)).join('')
    :`<p class="subtitle">${entries.length?'Ningún Pokémon coincide con los filtros.':'No hay Pokémon en el equipo ni en las cajas leídas.'}</p>`;
  $('builder-report').innerHTML=builderReport(team,abilities,entries);
  renderBuilderSaved();
  if(builderPickerSlot!==null)renderBuilderPicker();
  // The lists were rebuilt: put the keyboard focus back on the control that was used.
  if(focused)for(const node of document.querySelectorAll('#team-builder [data-focus]'))if(node.dataset.focus===focused&&!node.disabled){node.focus({preventScroll:true});break}
}
function builderEntry(id){return builderEntries().find(entry=>entry.id===id)||null}
function builderToggle(id){
  const index=builderMembers.findIndex(member=>member.id===id);
  if(index>=0)builderMembers=builderMembers.filter((_,i)=>i!==index);
  else if(builderMembers.length<TeamInsights.MAX_TEAM){
    const entry=builderEntry(id);
    if(entry)builderMembers=[...builderMembers,TeamInsights.memberOf(entry)];
  }
  renderTeamBuilder();
}
function builderMove(index,step){
  const target=index+step;
  if(index<0||target<0||index>=builderMembers.length||target>=builderMembers.length)return;
  const next=builderMembers.slice();
  [next[index],next[target]]=[next[target],next[index]];
  builderMembers=next;
  renderTeamBuilder();
}
function builderClick(event){
  const button=event.target.closest('button');
  if(!button||button.disabled)return;
  const data=button.dataset;
  if(data.builderSlot!==undefined)builderOpenPicker(Number(data.builderSlot));
  else if(data.builderToggle!==undefined)builderToggle(data.builderToggle);
  else if(data.builderRemove!==undefined){builderMembers=builderMembers.filter((_,i)=>i!==Number(data.builderRemove));renderTeamBuilder()}
  else if(data.builderSwap!==undefined){const [out,id]=data.builderSwap.split('|');builderSwap(out,id)}
  else if(data.builderMove!==undefined){const [index,step]=data.builderMove.split(':').map(Number);builderMove(index,step)}
}
$('team-builder').addEventListener('click',builderClick);
$('builder-use-party').onclick=()=>{
  builderClosePicker();
  builderMembers=builderEntries().filter(entry=>entry.kind==='party'&&!entry.egg&&($('builder-dead').checked||!entry.dead)).slice(0,TeamInsights.MAX_TEAM).map(TeamInsights.memberOf);
  renderTeamBuilder();
};
$('builder-clear').onclick=()=>{builderClosePicker();builderMembers=[];renderTeamBuilder()};
$('builder-search').oninput=renderTeamBuilder;
for(const id of ['builder-type','builder-source','builder-sort','builder-dead','builder-abilities'])$(id).onchange=renderTeamBuilder;
// --- Saved teams: local to this run and game (GET/POST /api/teams). Nothing here reaches the game or the network.
let builderTeams=[],builderOpenId=null,builderReadOnly=true,builderNotice='',builderRequest=0,builderStoreScope='';
const builderOpenTeam=()=>builderTeams.find(team=>team.id===builderOpenId)||null;
function builderDirty(){
  const open=builderOpenTeam();
  return open?JSON.stringify(open.members.map(m=>m.id))!==JSON.stringify(builderMembers.map(m=>m.id)):builderMembers.length>0;
}
function builderSavedMessage(text){builderNotice=text;setText($('builder-saved-status'),text)}
function applyBuilderTeams(result){
  builderTeams=list(result.teams).filter(team=>team&&typeof team==='object'&&typeof team.id==='string'&&Array.isArray(team.members));
  builderStoreScope=typeof result.scope==='string'?result.scope:'';
  builderReadOnly=result.read_only===true||!builderStoreScope;
  if(!builderOpenTeam())builderOpenId=null;
  builderSignature='';
}
async function loadBuilderTeams(){
  const request=++builderRequest;
  builderReadOnly=true;builderStoreScope='';builderSignature='';
  if(companionView){applyBuilderTeams({teams:[]});return}
  try{
    const result=await getJSON('/api/teams');
    if(request!==builderRequest)return;
    applyBuilderTeams(result);
    builderSavedMessage(typeof result.notice==='string'?result.notice:'');
  }catch(error){
    if(request===builderRequest)builderSavedMessage('No se pudieron cargar los equipos guardados.');
  }
  if(teamBuilderActive())renderTeamBuilder();
}
async function builderTeamRequest(payload,done){
  if(companionView)return;
  if(builderReadOnly||!builderStoreScope){builderSavedMessage('Vuelve a abrir el asistente para cargar los equipos de esta partida antes de guardar.');return}
  const request=++builderRequest;
  try{
    const response=await fetch('/api/teams',{method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify({...payload,scope:builderStoreScope})});
    const result=await response.json();
    if(!response.ok)throw Error(result.error||'No se pudo guardar el equipo.');
    if(request!==builderRequest)return;
    applyBuilderTeams(result);
    builderOpenId=typeof result.team==='string'?result.team:null;
    const open=builderOpenTeam();
    if(open)$('builder-name').value=open.name;
    builderSavedMessage(done);
  }catch(error){
    builderSavedMessage(error.message);
  }
  renderTeamBuilder();
}
function renderBuilderSaved(){
  const select=$('builder-saved'),open=builderOpenTeam(),locked=companionView||builderReadOnly;
  select.replaceChildren();
  select.add(new Option('Borrador sin guardar',''));
  for(const team of builderTeams)select.add(new Option(`${team.name} (${team.members.length})`,team.id));
  select.value=builderOpenId||'';
  select.disabled=companionView;
  $('builder-name').disabled=locked;
  $('builder-save').disabled=locked||!builderMembers.length;
  $('builder-save').textContent=open?'Guardar cambios':'Guardar equipo';
  for(const id of ['builder-rename','builder-duplicate','builder-delete'])$(id).disabled=locked||!open;
  const count=`${builderTeams.length} equipo${builderTeams.length===1?'':'s'} guardado${builderTeams.length===1?'':'s'} en esta partida y juego.`;
  const info=companionView?'Los equipos se guardan solo en tu propia partida.'
    :open?`${open.name} · ${open.game||''} · modificado ${String(open.modified||'').slice(0,10)}${builderDirty()?' · cambios sin guardar':''}`
    :builderMembers.length?'Borrador sin guardar. '+count:count;
  setText($('builder-saved-info'),info);
  setText($('builder-saved-status'),builderNotice);
}
$('builder-saved').onchange=()=>{
  const team=builderTeams.find(item=>item.id===$('builder-saved').value)||null;
  if(builderDirty()&&!confirm('El equipo virtual tiene cambios sin guardar. ¿Abrir otro equipo y descartarlos?')){$('builder-saved').value=builderOpenId||'';return}
  builderOpenId=team?team.id:null;
  builderMembers=team?team.members.slice(0,TeamInsights.MAX_TEAM).map(m=>({id:String(m.id),species_id:Number(m.species_id)||0,species:String(m.species??''),nickname:String(m.nickname??'')})):[];
  $('builder-name').value=team?team.name:'';
  builderSavedMessage('');
  renderTeamBuilder();
};
$('builder-save').onclick=()=>{
  const name=$('builder-name').value.trim();
  if(!name){builderSavedMessage('Escribe un nombre para el equipo.');$('builder-name').focus();return}
  return builderTeamRequest({action:'save',name,members:builderMembers,...(builderOpenId?{id:builderOpenId}:{})},'Equipo guardado.');
};
$('builder-rename').onclick=()=>{
  const name=$('builder-name').value.trim();
  if(!name){builderSavedMessage('Escribe el nuevo nombre.');$('builder-name').focus();return}
  if(builderOpenId)return builderTeamRequest({action:'rename',id:builderOpenId,name},'Nombre cambiado.');
};
$('builder-duplicate').onclick=()=>{if(builderOpenId)return builderTeamRequest({action:'duplicate',id:builderOpenId},'Equipo duplicado. Ahora editas la copia.')};
$('builder-delete').onclick=()=>{
  const open=builderOpenTeam();
  if(!open||!confirm(`¿Eliminar el equipo guardado «${open.name}»? No se puede deshacer.`))return;
  return builderTeamRequest({action:'delete',id:open.id,confirm:true},'Equipo eliminado. Sus integrantes siguen en el borrador.');
};
// --- Recommendations: explained, rule-based suggestions from TeamInsights. Applying one only edits the draft.
const builderSigned=value=>(value>0?'+':'')+String(Math.round(value*10)/10).replace('.',',');
const builderStatistics=change=>change.statistics?.reason?`<span>${esc(change.statistics.reason)}</span>`:'';
function builderChange(change){
  return `<span>${change.gains.length?change.gains.map(text=>esc(text)).join('; '):'Sin mejora clara de cobertura'}.</span>`
    +builderStatistics(change)
    +(change.losses.length?`<span class="builder-cost">A cambio: ${change.losses.map(text=>esc(text)).join('; ')}.</span>`:'<span class="builder-cost">Sin nuevas debilidades compartidas ni pérdida de cobertura.</span>');
}
function builderCandidateName(entry){
  const p=entry.pokemon;
  return `<b>${esc(TeamInsights.label(p))}</b> <small>${list(p.types).map(type=>esc(type)).join(' / ')||'—'} · ${builderPlace(entry)}${entry.historical?' · lectura guardada':''}</small>`;
}
function builderEffects(change){
  const gained=change.gained||{},lost=change.lost||{};
  const benefits=[...list(gained.immunity).map(type=>'inmunidad a '+type),...list(gained.resist).map(type=>'resistencia a '+type),...list(gained.coverage).map(type=>'cobertura frente a '+type)];
  const costs=[...list(lost.immunity).map(type=>'pierde inmunidad a '+type),...list(lost.resist).map(type=>'pierde resistencia a '+type),...list(lost.coverage).map(type=>'pierde cobertura frente a '+type)];
  const gain=benefits.length?benefits:list(change.gains),risk=costs.length?costs:list(change.losses);
  return gain.slice(0,3).map(text=>`<span class="builder-effect gain">+ ${esc(text)}</span>`).join('')
    +risk.slice(0,2).map(text=>`<span class="builder-effect risk">− ${esc(text)}</span>`).join('');
}
function builderRecommendation(change,action='add'){
  const entry=change.entry,p=entry.pokemon,total=TeamInsights.bst(p),swap=action==='swap',picker=action==='pick';
  const label=swap?'Aplicar al borrador':picker?'Elegir':'Añadir al borrador';
  const data=swap?`data-builder-swap="${esc(TeamInsights.pokemonId(change.out))}|${esc(entry.id)}"`:picker?`data-builder-pick="${esc(entry.id)}"`:`data-builder-toggle="${esc(entry.id)}"`;
  const reason=list(change.gained?.immunity).length?'Inmunidad a '+change.gained.immunity[0]
    :list(change.gained?.coverage).length?'Cobertura frente a '+change.gained.coverage[0]
    :list(change.gained?.resist).length?'Resiste '+change.gained.resist[0]
    :list(change.gains).length?'Reduce debilidades compartidas':'Alternativa disponible; revisa los riesgos.';
  return `<article class="builder-recommendation">${builderSprite(p.sprite_id||p.species_id)}<div class="builder-recommendation-name"><strong>${esc(TeamInsights.label(p))}</strong><small>${esc(p.species)}${p.analysis_mega?' · '+esc(p.analysis_preview_label||'Mega simulada'):''}</small><div class="builder-chip-row">${builderTypeChips(p.types)}</div></div>`
    +`<div class="builder-recommendation-bst"><strong>${total===null?'—':num(total)}</strong><small>BST</small></div>`
    +(swap?`<p class="builder-swap-caption">Sustituir a <b>${esc(TeamInsights.label(change.out))}</b> por <b>${esc(TeamInsights.label(p))}</b></p>`:'')
    +`<p class="builder-recommendation-reason">${esc(reason)}</p><div class="builder-chip-row builder-recommendation-effects">${builderEffects(change)}</div>`
    +`<details class="builder-recommendation-detail"><summary>Ver motivos</summary><p class="subtitle">${builderPlace(entry)}${entry.historical?' · lectura guardada':''}</p><div>Motivo: ${builderChange(change)}</div></details>`
    +`<button type="button" class="${picker?'primary':''}" ${data}>${label}</button></article>`;
}
function builderAdvice(evaluation,entries,abilities){
  const types=analysisData.types,chart=analysisData.chart;
  const notes=TeamInsights.teamNotes(evaluation),selected=new Set(builderMembers.map(member=>member.id));
  const result=TeamInsights.suggestChanges(chart,types,evaluation.members,entries.filter(entry=>!selected.has(entry.id)),abilities);
  return '<section class="builder-advice" aria-label="Recomendaciones">'
    +(builderMembers.length<TeamInsights.MAX_TEAM?'<div class="builder-advice-heading"><h3>Incorporaciones posibles</h3><button type="button" data-builder-slot="'+builderMembers.length+'">Ver opciones para el siguiente hueco</button></div><div class="builder-recommendation-grid">'+result.additions.slice(0,3).map(item=>builderRecommendation(item)).join('')+(result.additions.length?'':'<p class="subtitle">No hay mejoras claras de cobertura. Puedes elegir otro Pokémon en un hueco libre.</p>')+'</div>':'')
    +'<details class="builder-detail"><summary>Sustituciones posibles'+(result.swaps.length?' · '+result.swaps.length:'')+'</summary><div class="builder-recommendation-grid">'
    +result.swaps.map(item=>builderRecommendation(item,'swap')).join('')+(result.swaps.length?'':'<p class="subtitle">No hay sustituciones con una mejora clara.</p>')+'</div></details>'
    +'<details class="builder-detail"><summary>Cómo se valoran las sugerencias</summary>'
    +builderList('Lectura defensiva',notes.defensive.map(text=>esc(text)),'Sin debilidades compartidas.')
    +builderList('Lectura ofensiva',notes.offensive.map(text=>esc(text)),'Sin observaciones.')
    +`<p class="subtitle">Se compararon ${result.considered} candidatos.${result.skipped?` Quedaron ${result.skipped} sin comparar.`:''} Primero se valora cobertura y sinergia; entre opciones parecidas se considera BST, distribución de bases y nivel conocido. Los valores desconocidos no se inventan. No calcula daño, objetos ni las reglas de tu partida: son opciones para valorar, no «el mejor equipo».</p></details></section>`;
}
function builderSwap(out,id){
  const index=builderMembers.findIndex(member=>member.id===out);
  const entry=builderEntry(id);
  if(!entry||index<0||index>=builderMembers.length||builderMembers.some(member=>member.id===id))return;
  builderMembers=builderMembers.map((member,i)=>i===index?TeamInsights.memberOf(entry):member);
  renderTeamBuilder();
}
// Guided, explicit selection. Opening a slot never edits the draft.
function builderClosePicker(){
  builderPickerSlot=null;builderPickerScope='';
  const dialog=$('builder-picker');
  if(dialog?.open&&typeof dialog.close==='function')dialog.close();
}
function builderPickerRestoreFocus(){
  const slot=document.querySelector?.(`#team-builder [data-builder-slot="${builderMembers.length}"]`);
  (slot||$('builder-complete'))?.focus({preventScroll:true});
}
function builderOpenPicker(index=builderMembers.length){
  if(builderMembers.length>=TeamInsights.MAX_TEAM){builderSavedMessage('El equipo virtual ya tiene seis integrantes.');return}
  if(!Number.isInteger(index)||index<builderMembers.length||index>=TeamInsights.MAX_TEAM)return;
  builderPickerSlot=builderMembers.length;builderPickerLimit=6;builderPickerScope=builderScope();
  renderBuilderPicker();
  const dialog=$('builder-picker');
  if(!dialog.open&&typeof dialog.showModal==='function')dialog.showModal();
}
function builderPickerChoices(){
  const entries=builderEntries(),selected=new Set(builderMembers.map(member=>member.id));
  const pool=entries.filter(entry=>!selected.has(entry.id)&&!entry.dead&&!entry.egg);
  const team=TeamInsights.resolveTeam(builderMembers,entries).filter(item=>item.entry).map(item=>item.entry.pokemon);
  const ranked=TeamInsights.suggestChanges(analysisData.chart,analysisData.types,team,pool,$('builder-abilities').checked,builderPickerLimit).additions;
  const offered=new Set(ranked.map(item=>item.entry.id));
  // Even an empty or unusual team can be started; extra choices are labelled without invented benefits.
  const remaining=TeamInsights.sortEntries(pool.filter(entry=>!offered.has(entry.id)),'bst','desc');
  const before=TeamInsights.evaluateTeam(analysisData.chart,analysisData.types,team,$('builder-abilities').checked);
  const supplemental=remaining.map(entry=>({entry,...TeamInsights.compareTeams(before,TeamInsights.evaluateTeam(analysisData.chart,analysisData.types,[...team,entry.pokemon],$('builder-abilities').checked)),statistics:null}));
  return {choices:[...ranked,...supplemental],ranked:ranked.length};
}
function renderBuilderPicker(){
  if(builderPickerSlot===null)return;
  if(builderScope()!==builderPickerScope||builderMembers.length>=TeamInsights.MAX_TEAM){builderClosePicker();return}
  const {choices}=builderPickerChoices(),shown=choices.slice(0,builderPickerLimit);
  setText($('builder-picker-title'),`Elige para el hueco ${builderMembers.length+1}`);
  setText($('builder-picker-status'),'Tú decides cada incorporación. El equipo del juego no cambia.');
  $('builder-picker-options').innerHTML=shown.length?shown.map(item=>builderRecommendation(item,'pick')).join(''):'<p class="subtitle">No quedan Pokémon disponibles en las cajas leídas. Revisa la lectura o los integrantes elegidos.</p>';
  $('builder-picker-more').hidden=choices.length<=shown.length;
}
function builderPick(id){
  if(builderPickerSlot===null||builderPickerScope!==builderScope()||builderMembers.length>=TeamInsights.MAX_TEAM)return;
  const entry=builderEntry(id);
  if(!entry||entry.dead||entry.egg||builderMembers.some(member=>member.id===id))return;
  builderMembers=[...builderMembers,TeamInsights.memberOf(entry)];
  builderSavedMessage(`${TeamInsights.label(entry.pokemon)} añadido al borrador.`);
  builderPickerSlot=builderMembers.length;
  if(builderMembers.length>=TeamInsights.MAX_TEAM)builderClosePicker();
  renderTeamBuilder();
  if($('builder-picker').open)$('builder-picker-options').querySelector?.('[data-builder-pick]')?.focus({preventScroll:true});
}
$('builder-complete').onclick=()=>builderOpenPicker(builderMembers.length);
$('builder-picker-close').onclick=builderClosePicker;
$('builder-picker-more').onclick=()=>{builderPickerLimit+=6;renderBuilderPicker()};
$('builder-picker-options').addEventListener('click',event=>{
  const button=event.target.closest('[data-builder-pick]');
  if(button&&!button.disabled)builderPick(button.dataset.builderPick);
});
$('builder-picker').addEventListener('close',()=>{builderPickerSlot=null;builderPickerScope='';builderPickerRestoreFocus()});
// --- Move advisor: what the known moves cover and which attack types would add coverage.
// A concrete move is named only when the snapshot carries evidence that the Pokémon can learn it.
const MOVE_EVIDENCE={known:'Movimiento conocido',verified:'Disponible en datos verificables',generic:'Sugerencia genérica de tipo',missing:'Información no disponible'};
const moveTag=kind=>`<span class="move-evidence move-evidence-${kind}">${MOVE_EVIDENCE[kind]}</span>`;
function builderMoves(evaluation,abilities){
  if(!evaluation.size)return '';
  const advice=TeamInsights.moveAdvice(analysisData.chart,analysisData.types,evaluation,abilities);
  const byType=advice.attackTypes.map(a=>`<b>${esc(a.type)}</b> ×${a.count}: ${a.moves.map(m=>`${esc(m.name)} (${esc(m.pokemon)})`).join(', ')}`);
  const repeats=[
    ...advice.stacked.map(a=>`El equipo tiene ${a.count} ataques de tipo <b>${esc(a.type)}</b>.`),
    ...advice.room.flatMap(r=>r.repeated.map(x=>`${esc(r.pokemon)} conoce ${x.moves.length} ataques de tipo <b>${esc(x.type)}</b>: ${x.moves.map(name=>esc(name)).join(', ')}.`))
  ];
  const weak=[
    ...(advice.uncovered.length?[`Sin ataque supereficaz: ${advice.uncovered.map(type=>esc(type)).join(', ')}.`]:[]),
    ...advice.thin.map(t=>`<b>${esc(t.type)}</b>: un solo ataque supereficaz, ${esc(t.move)} de ${esc(t.pokemon)}.`)
  ];
  const suggestions=advice.suggestions.map(s=>
    `${moveTag('generic')} Un movimiento de tipo <b>${esc(s.type)}</b>`
    +(s.covers.length?` añadiría cobertura frente a ${s.covers.map(type=>esc(type)).join(', ')}`:'')
    +(s.reinforces.length?`${s.covers.length?' y':''} reforzaría la de ${s.reinforces.map(type=>esc(type)).join(', ')}`:'')+'.');
  const learnable=advice.learnable.map(l=>`${moveTag('verified')} ${esc(l.pokemon)} puede aprender <b>${esc(l.move)}</b> (${esc(l.type)}) según ${esc(l.source)}.`);
  const room=advice.room.filter(r=>r.free).map(r=>`${esc(r.pokemon)} tiene ${r.free} ${r.free===1?'espacio libre':'espacios libres'} de movimiento.`);
  const known=evaluation.knownMoves;
  return '<section class="builder-advice builder-moves" aria-label="Asesor de movimientos"><h3 class="builder-section-title">Asesor de movimientos</h3>'
    +(advice.lines.length?`<p class="builder-headline">${advice.lines.map(text=>esc(text)).join(' ')}</p>`:'')
    +'<div class="builder-cards">'
    +builderList(`Ataques por tipo ${moveTag('known')}`,byType,'No se conocen movimientos ofensivos de este equipo.')
    +builderList('Redundancias',repeats,known?'Ningún tipo de ataque se repite tres veces ni dos en un mismo Pokémon.':'Sin movimientos ofensivos conocidos.')
    +builderList('Tipos enemigos con poca cobertura',weak,known?'Cada tipo recibe ataques supereficaces de dos o más movimientos.':'Sin movimientos ofensivos conocidos.')
    +builderList('Tipos de movimiento recomendados',[...learnable,...suggestions],known?'Ningún tipo de ataque nuevo añadiría cobertura.':'Añade Pokémon con movimientos conocidos para recibir sugerencias.')
    +builderList('Quién tiene sitio',room,'Todos los integrantes conocen cuatro movimientos.')
    +'</div>'
    +`<p class="subtitle">${advice.hasLearnsets?'Los movimientos concretos proceden de los datos importados de esta partida.'
      :`${moveTag('missing')} El Tracker no tiene datos de aprendizaje (nivel, MT o tutores) de esta partida, y la ROM puede estar randomizada: por eso solo se sugieren tipos de movimiento, no movimientos concretos.`}`
    +' Los ataques se leen de los movimientos que cada Pokémon conoce ahora. El asesor no cambia movimientos en el juego.</p>'
    +'</section>';
}
$('analysis-section-current').onclick=()=>setAnalysisSection('current');
$('analysis-section-builder').onclick=()=>setAnalysisSection('builder');
