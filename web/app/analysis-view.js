'use strict';
// Type analysis view (rules live in /analysis.js).
function multiplier(value){return value===null?'—':`${Number(value.toFixed(3))}×`}
function cellClass(value){return value===0?'immune':value>1?'weak':value<1?'resist':'neutral'}
function renderAnalysis(){
  if(!state||!analysisData)return;
  const team=state.party.filter(Boolean);
  syncAnalysisSelectors(team);
  const simple=$('analysis-defense').value==='simple';
  const mode=$('analysis-mode').value,abilities=$('analysis-abilities').checked,dual=$('analysis-dual').checked,a=$('analysis-a').value,b=$('analysis-b').value;
  $('analysis-defense-label').hidden=mode!=='defense';
  $('analysis-a-label').hidden=mode==='defense';
  $('analysis-b-label').hidden=mode!=='double';
  $('analysis-dual-label').hidden=mode==='defense';
  const signature=JSON.stringify([team.map(p=>[p.types,p.ability_id,p.analysis_moves,p.slot,p.nickname]),mode,a,b,abilities,dual,simple]);
  if(signature===analysisSignature)return;
  analysisSignature=signature;
  const content=$('analysis-content');
  if(!team.length){content.innerHTML='<p class="subtitle">Sin Pokémon en el equipo.</p>';return}
  const types=analysisData.types,chart=analysisData.chart;
  if(mode==='defense'){content.innerHTML=defenseTable(team,types,chart,abilities,simple);return}
  const chosen=team.filter(p=>String(p.slot)===a||(mode==='double'&&String(p.slot)===b));
  if(mode==='double'&&(chosen.length<2||a===b)){content.innerHTML='<p class="subtitle">Selecciona dos Pokémon diferentes del equipo.</p>';return}
  content.innerHTML=coverageReport(chosen,types,chart,abilities,dual);
}
// Rebuilds the Pokémon pickers only when the team changes, keeping the current choice.
function syncAnalysisSelectors(team){
  const teamSig=JSON.stringify(team.map(p=>[p.slot,p.nickname,p.species]));
  if(teamSig===analysisTeamSignature)return;
  analysisTeamSignature=teamSig;
  for(const id of ['analysis-a','analysis-b']){
    const before=$(id).value;
    $(id).replaceChildren();
    for(const p of team)$(id).add(new Option(`${p.nickname||p.species} · ${p.species}`,String(p.slot)));
    if(team.some(p=>String(p.slot)===before))$(id).value=before;
  }
  if($('analysis-b').value===$('analysis-a').value&&team.length>1)$('analysis-b').value=String(team[1].slot);
}
function defenseTable(team,types,chart,abilities,simple){
  const teamHeaders=simple?'':team.map(p=>
    `<th>${esc(p.nickname||p.species)}<small>${esc(list(p.types).join(' / '))}<br>${abilities?esc(p.ability):''}</small></th>`
  ).join('');
  const rows=types.map(type=>{
    const values=team.map(p=>TypeAnalysis.defensive(chart,type,p,abilities));
    const cells=simple?'':values.map(v=>`<td class="${cellClass(v)}">${multiplier(v)}</td>`).join('');
    return `<tr><th>${esc(type)}</th>${cells}`
      +`<td>${values.filter(v=>v>1).length}</td>`
      +`<td>${values.filter(v=>v>0&&v<1).length}</td>`
      +`<td>${values.filter(v=>v===0).length}</td></tr>`;
  }).join('');
  return '<div class="analysis-scroll">'
    +`<table class="analysis-table ${simple?'analysis-simple':''}">`
    +`<caption>${simple?'Pokémon por tipo · Sin neutrales':'Efectividad defensiva'}</caption>`
    +`<thead><tr><th>Tipo atacante</th>${teamHeaders}<th>Débiles</th><th>Resisten</th><th>Inmunes</th></tr></thead>`
    +`<tbody>${rows}</tbody>`
    +'</table></div>';
}
function coverageReport(chosen,types,chart,abilities,dual){
  const moves=chosen.flatMap(p=>list(p.analysis_moves).filter(m=>m&&m.category!=='Estado').map(m=>[m,p]));
  const targets=types.map(t=>[t]);
  if(dual)for(let i=0;i<types.length;i++)for(let j=i+1;j<types.length;j++)targets.push([types[i],types[j]]);
  const results=targets.map(target=>({target,best:TypeAnalysis.coverage(chart,chosen,target,abilities)}));
  const moveList=moves.map(([m,p])=>
    `<span>${esc(m.name)} <small>${esc(TypeAnalysis.attackType(m,p,abilities))} · ${esc(p.nickname||p.species)}</small></span>`
  ).join('')||'<p>No hay movimientos ofensivos disponibles.</p>';
  const cells=results.map(({target,best})=>
    `<article class="coverage-cell ${best?cellClass(best.value):'neutral'}">`
    +`<strong>${esc(target.join(' / '))}</strong>`
    +`<b>${multiplier(best?.value??null)}</b>`
    +`<small>${best?esc(best.move.name)+' · '+esc(best.pokemon.nickname||best.pokemon.species):'Sin ataque'}</small>`
    +'</article>'
  ).join('');
  return `<div class="coverage-moves">${moveList}</div>`
    +'<p class="subtitle">Mejor cobertura · Sin sumar ataques</p>'
    +'<div class="coverage-summary">'
    +`<span>${results.filter(r=>r.best?.value>1).length} supereficaces</span>`
    +`<span>${results.filter(r=>r.best?.value===1).length} neutrales</span>`
    +`<span>${results.filter(r=>r.best&&r.best.value<1).length} resistidos / inmunes</span>`
    +'</div>'
    +`<div class="coverage-grid">${cells}</div>`;
}
for(const id of ['analysis-defense','analysis-mode','analysis-a','analysis-b','analysis-abilities','analysis-dual'])$(id).onchange=renderAnalysis;
