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
function builderReport(team,abilities){
  if(!team.length)return '<p class="subtitle">Añade Pokémon al equipo virtual para ver su cobertura.</p>';
  const types=analysisData.types,chart=analysisData.chart;
  const evaluation=TeamInsights.evaluateTeam(chart,types,team,abilities);
  return builderSummary(evaluation)
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
  if(scope!==builderContext){builderContext=scope;builderMembers=[];builderSignature=''}
  const entries=TeamInsights.candidateEntries(state);
  syncBuilderTypes(entries);
  const sort=$('builder-sort').value,abilities=$('builder-abilities').checked;
  const filters={query:$('builder-search').value,type:$('builder-type').value,kind:$('builder-source').value,hideDead:!$('builder-dead').checked,hideEggs:true};
  const signature=JSON.stringify([scope,builderMembers,filters,sort,abilities,state.stale,state.connection?.status,state.box_verified,
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
  $('builder-report').innerHTML=builderReport(team,abilities);
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
$('analysis-section-current').onclick=()=>setAnalysisSection('current');
$('analysis-section-builder').onclick=()=>setAnalysisSection('builder');
