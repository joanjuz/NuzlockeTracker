'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm');
const A=require('../web/analysis.js'),I=require('../web/insights.js');
const {loadShared,slice}=require('./ui_shared.js');
const {types,chart}=require('../data/Analysis_USUM.json');
const ctx={TypeAnalysis:A,TeamInsights:I};vm.createContext(ctx);loadShared(ctx);
vm.runInContext(slice('app/analysis-view.js','function multiplier(',"\nfor(const id of ['analysis-defense'"),ctx);
function overviewKeepsThreatsAndRealCoverage(){
  const team=[{nickname:'Uno',types:['Fuego'],analysis_moves:[{name:'Ascuas',type:'Fuego',category:'Especial'}]},{nickname:'Dos',types:['Roca'],analysis_moves:[]}];
  const html=ctx.analysisOverview(team,types,chart,true);
  assert.match(html,/Amenazas principales/);assert.match(html,/Agua/);assert.match(html,/Falta cobertura/);
  assert.match(html,/Puntos fuertes/);assert.ok(!html.includes('<table'));
  const chartHtml=ctx.defenseChart(team,types,chart,true,'weak');
  assert.equal((chartHtml.match(/<details class="fx-row">/g)||[]).length,18);
  assert.match(chartHtml,/Uno/);assert.match(chartHtml,/2×/);
}
function overviewEscapesUnknownAndHostileData(){
  const html=ctx.analysisOverview([{nickname:'<img src=x>',types:['<img src=x>'],analysis_moves:[]}],['<img src=x>'],chart,true);
  assert.ok(!html.includes('<img src=x>'));assert.match(html,/Sin ataques conocidos/);
}
for(const test of [overviewKeepsThreatsAndRealCoverage,overviewEscapesUnknownAndHostileData]){test();console.log(test.name+': OK')}
