'use strict';
const assert=require('node:assert/strict'),I=require('../web/insights.js');
const {chart,types}=require('../data/Analysis_USUM.json');
const mon=(id,type,n)=>({species_id:id,species:'Ejemplar '+id,encryption_constant:id,origin_version:33,types:[type],ability_id:0,
  base_stats:n?{HP:n,ATK:n,DEF:n,SPA:n,SPD:n,SPE:n}:null,analysis_moves:[{name:'Ataque',type,category:'Físico'}]});
const entry=pokemon=>({id:I.pokemonId(pokemon),pokemon,kind:'box',dead:false,egg:false});
function equivalentCoveragePrefersStrongerCandidate(){
  const team=[mon(1,'Normal',null)],weak=entry(mon(2,'Agua',40)),strong=entry(mon(3,'Agua',100));
  const result=I.suggestChanges(chart,types,team,[weak,strong],true);
  assert.equal(result.additions[0].entry.id,strong.id);
  assert.equal(result.additions[0].delta,result.additions[1].delta);
  assert.equal(result.additions[0].ranking.bst,600);
  assert.equal(result.additions[0].statistics,null,'No invented team comparison when old bases are unknown');
  assert.deepEqual(I.suggestChanges(chart,types,team,[weak,strong],true),result);
}
function qualityDoesNotMakeRedundantCandidateUseful(){
  const team=[mon(1,'Normal',50)],redundant=entry(mon(2,'Normal',150)),useful=entry(mon(3,'Lucha',50));
  const result=I.suggestChanges(chart,types,team,[redundant,useful],true);
  assert.ok(result.additions.some(item=>item.entry.id===useful.id));
  assert.ok(!result.additions.some(item=>item.entry.id===redundant.id));
}
function projectedClonesCannotDuplicateSelectedSpecimen(){
  const p=mon(1,'Normal',50);
  const result=I.suggestChanges(chart,types,[p],[entry({...p,types:['Agua']})],true);
  assert.equal(result.considered,0);
}
function substantialCoverageOutranksRawStrength(){
  const team=[mon(1,'Normal',50)],strong=entry(mon(2,'Dragón',150)),coverage=entry(mon(3,'Acero',45));
  const result=I.suggestChanges(chart,types,team,[strong,coverage],true);
  assert.equal(result.additions[0].entry.id,coverage.id);
  assert.ok(result.additions[0].ranking.band>result.additions[1].ranking.band);
}
function strongCandidateAtEndOfFullPCIsConsidered(){
  const pool=Array.from({length:960},(_,i)=>entry(mon(i+2,'Agua',i===959?100:40)));
  const result=I.suggestChanges(chart,types,[mon(1,'Normal',50)],pool,true);
  assert.equal(result.additions[0].entry.id,'33:961');
  assert.equal(result.skipped,0);
}
for(const test of [equivalentCoveragePrefersStrongerCandidate,qualityDoesNotMakeRedundantCandidateUseful,projectedClonesCannotDuplicateSelectedSpecimen,substantialCoverageOutranksRawStrength,strongCandidateAtEndOfFullPCIsConsidered]){test();console.log(test.name+': OK')}
