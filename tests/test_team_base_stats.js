'use strict';
// Imported base stats may break coverage ties, never replace matchup analysis.
const assert=require('node:assert/strict');
const I=require('../web/insights.js');
const {chart,types}=require('../data/Analysis_USUM.json');
const bases=(HP,ATK,DEF,SPA,SPD,SPE)=>({HP,ATK,DEF,SPA,SPD,SPE});
const mon=(id,type,base_stats,category='Físico')=>({species_id:id,species:'Ejemplar '+id,types:[type],base_stats,
  encryption_constant:id,origin_version:33,ability_id:0,analysis_moves:[{id:1,name:'Ataque conocido',type,category}]});
const entry=pokemon=>({id:I.pokemonId(pokemon),pokemon,kind:'box',dead:false,egg:false});
function stats_follow_known_attack_category(){
  const physical=mon(1,'Normal',bases(100,120,81,30,100,80));
  const profile=I.baseStatProfile([physical]);
  assert.equal(profile.offense,120);
  assert.equal(profile.physicalBulk,90); // sqrt(100*81)
  assert.equal(profile.specialBulk,100);
  assert.equal(profile.speed,80);
  assert.equal(profile.score,97.5);
  assert.equal(I.baseStatProfile([{...physical,analysis_moves:[{type:'Normal',category:'Especial'}]}]).offense,30);
  assert.equal(I.baseStatProfile([{...physical,analysis_moves:[{type:'Normal',category:'Estado'}]}]).offense,0);
}
function unknown_bases_are_not_guessed(){
  for(const base_stats of [null,{},bases(50,50,50,50,50,undefined),bases(50,50,50,50,50,NaN)])
    assert.equal(I.baseStatProfile([mon(2,'Agua',base_stats)]),null);
  assert.equal(I.baseStatProfile([]),null);
}
function known_stats_break_equal_coverage_ties(){
  const party=[mon(1,'Normal',bases(70,70,70,70,70,70))];
  const low=entry(mon(2,'Agua',bases(50,30,50,250,50,50)));
  const useful=entry(mon(3,'Agua',bases(80,100,80,20,80,80)));
  const result=I.suggestChanges(chart,types,party,[low,useful],true);
  assert.equal(result.additions[0].entry.id,useful.id);
  assert.equal(result.additions[0].delta,result.additions[1].delta,'Coverage remains the primary score');
  assert.ok(result.additions[0].statistics.delta>result.additions[1].statistics.delta);
  assert.match(result.additions[0].statistics.reason,/Bases conocidas/);
  assert.equal(I.bst(low.pokemon)>I.bst(useful.pokemon),true,'Higher BST is not the winner');
  assert.deepEqual(I.suggestChanges(chart,types,party,[low,useful],true),result,'Deterministic');
}
function missing_team_stats_do_not_hide_known_candidate_quality(){
  const party=[mon(1,'Normal',null)];
  const a=entry(mon(2,'Agua',bases(50,50,50,50,50,50))),b=entry(mon(3,'Agua',bases(100,100,100,100,100,100)));
  const result=I.suggestChanges(chart,types,party,[a,b],true);
  assert.deepEqual(result.additions.map(item=>item.entry.id),[b.id,a.id]);
  assert.equal(result.additions[0].statistics,null);
  assert.equal(result.additions[1].statistics,null);
}
for(const test of [known_stats_break_equal_coverage_ties,stats_follow_known_attack_category,unknown_bases_are_not_guessed,missing_team_stats_do_not_hide_known_candidate_quality]){
  test();console.log(test.name+': OK');
}
