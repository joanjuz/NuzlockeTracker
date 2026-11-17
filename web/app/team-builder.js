'use strict';
// Team assistant: virtual teams built from the Pokémon the user owns (party and read boxes).
// Purely informative: it never sends a command and never changes the party in the game.
const BUILDER_CANDIDATE_LIMIT=120;
let analysisSection='current',builderMembers=[],builderContext='',builderSignature='',builderTypes='';
function teamBuilderActive(){return analysisSection==='builder'}
function setAnalysisSection(section){
  analysisSection=section==='builder'?'builder':'current';
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
  if(!item)return `<li class="builder-slot builder-slot-empty"><span>${index+1}</span><small>Espacio libre</small></li>`;
  const {member,entry,status}=item,p=entry?.pokemon;
  const name=p?TeamInsights.label(p):member.nickname||member.species||'Pokémon';
  const note=status==='missing'?'<small class="builder-warning">No localizado en el equipo ni en las cajas leídas</small>'
    :status==='changed'?`<small class="builder-warning">Antes era ${esc(member.species)}</small>`:'';
  const tags=p?`<small>${esc(p.species)} · ${list(p.types).map(type=>esc(type)).join(' / ')||'—'}</small><small>${builderPlace(entry)}${entry.dead?' · muerto':''}${entry.historical?' · lectura guardada':''}</small>`
    :`<small>${esc(member.species)}</small>`;
  return `<li class="builder-slot${status==='missing'?' builder-slot-missing':''}">`
    +builderSprite(p?p.species_id:member.species_id)
    +`<div><strong>${esc(name)}</strong>${tags}${note}</div>`
    +'<div class="builder-slot-actions">'
    +`<button type="button" data-builder-move="${index}:-1" data-focus="up${index}" aria-label="Subir a ${esc(name)}" ${index===0?'disabled':''}>↑</button>`
    +`<button type="button" data-builder-move="${index}:1" data-focus="down${index}" aria-label="Bajar a ${esc(name)}" ${index===count-1?'disabled':''}>↓</button>`
    +`<button type="button" data-builder-remove="${index}" data-focus="remove${index}" aria-label="Quitar a ${esc(name)} del equipo virtual">Quitar</button>`
    +'</div></li>';
}
function builderCandidate(entry,selected,full){
  const p=entry.pokemon,total=TeamInsights.bst(p);
  const hint=selected?'En el equipo virtual':full?'Equipo completo: quita o reemplaza un integrante':'Añadir al equipo virtual';
  return `<button type="button" class="builder-candidate" data-builder-toggle="${esc(entry.id)}" data-focus="c${esc(entry.id)}" aria-pressed="${selected}" title="${hint}" ${full&&!selected?'disabled':''}>`
    +builderSprite(p.species_id)
    +`<strong>${esc(TeamInsights.label(p))}</strong>`
    +`<small>${list(p.types).map(type=>esc(type)).join(' / ')||'—'}</small>`
    +`<small>${builderPlace(entry)}${total===null?'':' · BST '+num(total)}</small>`
    +(entry.dead||entry.historical?`<small class="builder-warning">${[entry.dead?'Muerto':'',entry.historical?'Lectura guardada':''].filter(Boolean).join(' · ')}</small>`:'')
    +'</button>';
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
  if(!team.length)return '<p class="subtitle">Añade Pokémon al equipo virtual para ver su cobertura.</p>';
  const types=analysisData.types,chart=analysisData.chart;
  const evaluation=TeamInsights.evaluateTeam(chart,types,team,abilities);
  return builderAdvice(evaluation,entries,abilities)
    +builderMoves(evaluation,abilities)
    +builderSummary(evaluation)
    +'<details class="builder-detail" open><summary>Defensa por tipo</summary>'+defenseChart(team,types,chart,abilities,'weak')+'</details>'
    +'<details class="builder-detail"><summary>Cobertura ofensiva por tipo</summary>'+coverageReport(team,types,chart,abilities,false)+'</details>';
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
  if(scope!==builderContext){builderContext=scope;builderMembers=[];builderSignature='';builderOpenId=null;builderTeams=[];builderNotice='';$('builder-name').value='';loadBuilderTeams()}
  const entries=TeamInsights.candidateEntries(state);
  syncBuilderTypes(entries);
  const sort=$('builder-sort').value,abilities=$('builder-abilities').checked;
  const filters={query:$('builder-search').value,type:$('builder-type').value,kind:$('builder-source').value,hideDead:!$('builder-dead').checked,hideEggs:true};
  const signature=JSON.stringify([scope,builderMembers,builderOpenId,builderTeams,builderReadOnly,filters,sort,abilities,state.stale,state.connection?.status,state.box_verified,
    entries.map(e=>[e.id,e.key,e.dead,e.egg,e.historical,e.pokemon.species_id,e.pokemon.species,e.pokemon.nickname,e.pokemon.types,e.pokemon.ability_id,
      e.pokemon.base_stats,e.pokemon.analysis_moves])]);
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
  // The lists were rebuilt: put the keyboard focus back on the control that was used.
  if(focused)for(const node of document.querySelectorAll('#team-builder [data-focus]'))if(node.dataset.focus===focused&&!node.disabled){node.focus({preventScroll:true});break}
}
function builderEntry(id){return TeamInsights.candidateEntries(state).find(entry=>entry.id===id)||null}
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
  if(data.builderToggle!==undefined)builderToggle(data.builderToggle);
  else if(data.builderRemove!==undefined){builderMembers=builderMembers.filter((_,i)=>i!==Number(data.builderRemove));renderTeamBuilder()}
  else if(data.builderSwap!==undefined){const cut=data.builderSwap.indexOf(':');builderSwap(Number(data.builderSwap.slice(0,cut)),data.builderSwap.slice(cut+1))}
  else if(data.builderMove!==undefined){const [index,step]=data.builderMove.split(':').map(Number);builderMove(index,step)}
}
$('team-builder').addEventListener('click',builderClick);
$('builder-use-party').onclick=()=>{
  builderMembers=TeamInsights.candidateEntries(state).filter(entry=>entry.kind==='party'&&!entry.egg).slice(0,TeamInsights.MAX_TEAM).map(TeamInsights.memberOf);
  renderTeamBuilder();
};
$('builder-clear').onclick=()=>{builderMembers=[];renderTeamBuilder()};
$('builder-search').oninput=renderTeamBuilder;
for(const id of ['builder-type','builder-source','builder-sort','builder-dead','builder-abilities'])$(id).onchange=renderTeamBuilder;
// --- Saved teams: local to this run and game (GET/POST /api/teams). Nothing here reaches the game or the network.
let builderTeams=[],builderOpenId=null,builderReadOnly=false,builderNotice='',builderRequest=0;
const builderOpenTeam=()=>builderTeams.find(team=>team.id===builderOpenId)||null;
function builderDirty(){
  const open=builderOpenTeam();
  return open?JSON.stringify(open.members.map(m=>m.id))!==JSON.stringify(builderMembers.map(m=>m.id)):builderMembers.length>0;
}
function builderSavedMessage(text){builderNotice=text;setText($('builder-saved-status'),text)}
function applyBuilderTeams(result){
  builderTeams=list(result.teams).filter(team=>team&&typeof team==='object'&&typeof team.id==='string'&&Array.isArray(team.members));
  builderReadOnly=result.read_only===true;
  if(!builderOpenTeam())builderOpenId=null;
  builderSignature='';
}
async function loadBuilderTeams(){
  const request=++builderRequest;
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
  const request=++builderRequest;
  try{
    const response=await fetch('/api/teams',{method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify(payload)});
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
function builderChange(change){
  return `<span>${change.gains.map(text=>esc(text)).join('; ')}.</span>`
    +(change.losses.length?`<span class="builder-cost">A cambio: ${change.losses.map(text=>esc(text)).join('; ')}.</span>`:'<span class="builder-cost">Sin nuevas debilidades compartidas ni pérdida de cobertura.</span>');
}
function builderCandidateName(entry){
  const p=entry.pokemon;
  return `<b>${esc(TeamInsights.label(p))}</b> <small>${list(p.types).map(type=>esc(type)).join(' / ')||'—'} · ${builderPlace(entry)}${entry.historical?' · lectura guardada':''}</small>`;
}
function builderAdvice(evaluation,entries,abilities){
  const types=analysisData.types,chart=analysisData.chart;
  const scores=TeamInsights.teamScores(evaluation),notes=TeamInsights.teamNotes(evaluation);
  const selected=new Set(builderMembers.map(member=>member.id));
  const result=TeamInsights.suggestChanges(chart,types,evaluation.members,entries.filter(entry=>!selected.has(entry.id)),abilities);
  const additions=result.additions.map(item=>
    `${builderCandidateName(item.entry)}${builderChange(item)}<button type="button" data-builder-toggle="${esc(item.entry.id)}" data-focus="add${esc(item.entry.id)}">Añadir al borrador</button>`);
  const swaps=result.swaps.map(item=>
    `Sustituir a <b>${esc(TeamInsights.label(item.out))}</b> por ${builderCandidateName(item.entry)}<span>Motivo: ${item.gains.map(text=>esc(text)).join('; ')}.</span>`
    +(item.losses.length?`<span class="builder-cost">Se perdería o empeoraría: ${item.losses.map(text=>esc(text)).join('; ')}.</span>`:'<span class="builder-cost">Sin nuevas debilidades compartidas ni pérdida de cobertura.</span>')
    +`<button type="button" data-builder-swap="${item.index}:${esc(item.entry.id)}" data-focus="swap${item.index}${esc(item.entry.id)}">Aplicar al borrador</button>`);
  const pool=result.considered?`Se compararon ${result.considered} candidatos${result.skipped?` (quedaron ${result.skipped} sin comparar)`:''}.`:'No hay otros candidatos con los que comparar.';
  return '<section class="builder-advice" aria-label="Recomendaciones">'
    +'<dl class="builder-measures">'
    +`<div><dt>Balance defensivo</dt><dd>${builderSigned(scores.defense)}</dd></div>`
    +`<div><dt>Tipos con ataque supereficaz</dt><dd>${evaluation.knownMoves?`${scores.covered} / ${evaluation.offense.length}`:'No disponible'}</dd></div>`
    +`<div><dt>Redundancias</dt><dd>${scores.redundancy}</dd></div>`
    +`<div><dt>Tipos distintos</dt><dd>${scores.diversity}</dd></div></dl>`
    +'<p class="subtitle">Medidas separadas para comparar cambios. El balance defensivo suma resistencias e inmunidades y resta debilidades; no es una nota del equipo.</p>'
    +'<div class="builder-cards">'
    +builderList('Lectura defensiva',notes.defensive.map(text=>esc(text)),'Sin debilidades compartidas ni tipos sin resistencia.')
    +builderList('Lectura ofensiva',notes.offensive.map(text=>esc(text)),'Sin observaciones.')
    +(evaluation.size<TeamInsights.MAX_TEAM?builderList('Incorporaciones posibles',additions,'Ningún candidato mejora la cobertura sin empeorar más de lo que aporta.'):'')
    +builderList('Sustituciones posibles',swaps,'Ninguna sustitución de un integrante mejora el conjunto según estas reglas.')
    +'</div>'
    +`<p class="subtitle">${pool} Las sugerencias comparan tipos, habilidades compatibles y movimientos conocidos, de una incorporación o una sustitución cada vez. No tienen en cuenta niveles, estadísticas, objetos ni las reglas de tu partida: son opciones para valorar, no «el mejor equipo».</p>`
    +'</section>';
}
function builderSwap(index,id){
  const entry=builderEntry(id);
  if(!entry||index<0||index>=builderMembers.length||builderMembers.some(member=>member.id===id))return;
  builderMembers=builderMembers.map((member,i)=>i===index?TeamInsights.memberOf(entry):member);
  renderTeamBuilder();
}
$('builder-complete').onclick=()=>{
  const entries=TeamInsights.candidateEntries(state),selected=new Set(builderMembers.map(member=>member.id));
  const team=TeamInsights.resolveTeam(builderMembers,entries).filter(item=>item.entry).map(item=>item.entry.pokemon);
  // Free slots only: members that are not located keep their place.
  const free=TeamInsights.MAX_TEAM-builderMembers.length;
  const added=TeamInsights.completeTeam(analysisData.chart,analysisData.types,team,entries.filter(entry=>!selected.has(entry.id)),$('builder-abilities').checked).slice(0,free);
  builderMembers=[...builderMembers,...added.map(item=>TeamInsights.memberOf(item.entry))];
  builderSavedMessage(added.length?`Se ${added.length===1?'añadió 1 sugerencia':`añadieron ${added.length} sugerencias`} al borrador. Puedes cambiarlas antes de guardar.`
    :free?'Ningún candidato mejora la cobertura del borrador según estas reglas.':'El equipo virtual ya tiene seis integrantes.');
  renderTeamBuilder();
};
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
