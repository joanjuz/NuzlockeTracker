'use strict';
// TeamInsights: counts and orderings built on TypeAnalysis, plus the bar chart markup.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const A=require('../web/analysis.js'),I=require('../web/insights.js');
const {loadShared,slice,read}=require('./ui_shared.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/Analysis_USUM.json'),'utf8'));
const {chart,types}=data;
let checks=0;const ok=(value,message)=>{assert.ok(value,message);checks++};const eq=(a,b,message)=>{assert.deepEqual(a,b,message);checks++};
eq(types.length,18,'Los 18 tipos');
const mon=(nickname,monTypes,ability_id=0)=>({nickname,species:nickname,types:monTypes,ability_id});
const team=[mon('Volca',['Bicho','Fuego']),mon('Milo',['Agua']),mon('Levi',['Veneno'],26),mon('Kingdra',['Agua','Dragón']),mon('Skarm',['Acero','Volador'])];

// --- defenseSummary: every member lands in exactly one bucket, straight from TypeAnalysis.defensive.
const rows=I.defenseSummary(chart,types,team,true);
eq(rows.length,18);
for(const row of rows){
  eq(row.total,team.length,row.type+': cada integrante cuenta una vez');
  for(const key of I.BUCKETS)for(const m of row[key])eq(m.value,A.defensive(chart,row.type,m.pokemon,true),'Sin reglas duplicadas');
}
const by=Object.fromEntries(rows.map(r=>[r.type,r]));
eq(by['Roca'].x4.map(m=>m.pokemon.nickname),['Volca'],'Debilidad ×4 separada de ×2');
eq(by['Eléctrico'].x2.map(m=>m.pokemon.nickname).sort(),['Milo','Skarm']);
eq(by['Roca'].weak,1);
eq(by['Fuego'].quarter.map(m=>m.pokemon.nickname),['Kingdra'],'Resistencia ×¼ separada de ×½');
eq(by['Fuego'].half.map(m=>m.pokemon.nickname),['Milo']);
eq(by['Fuego'].resist,2);
eq(by['Tierra'].immune.map(m=>m.pokemon.nickname).sort(),['Levi','Skarm'],'Levitación y Volador son inmunes a Tierra');
// Abilities off: Levitate no longer protects the Poison type.
const plain=Object.fromEntries(I.defenseSummary(chart,types,team,false).map(r=>[r.type,r]));
eq(plain['Tierra'].immune.map(m=>m.pokemon.nickname),['Skarm']);
eq(plain['Tierra'].x2.map(m=>m.pokemon.nickname),['Levi']);
eq(I.bucketOf(1.5),'x2','Filtro/Roca Sólida sigue siendo debilidad');
eq(I.bucketOf(.125),'quarter');
eq(I.defenseSummary(chart,types,[null,undefined],true)[0].total,0,'Los huecos del equipo no cuentan');
eq(I.defenseSummary(chart,null,team).length,0);

// --- sortDefense: stable, never mutates and falls back to chart order.
const before=rows.map(r=>r.type);
const weak=I.sortDefense(rows,'weak');
eq(rows.map(r=>r.type),before,'No reordena la lista original');
for(let i=1;i<weak.length;i++)ok(weak[i-1].weak>=weak[i].weak,'Mayor debilidad primero');
const resist=I.sortDefense(rows,'resist');
for(let i=1;i<resist.length;i++)ok(resist[i-1].resist+resist[i-1].immunities>=resist[i].resist+resist[i].immunities,'Mayor resistencia primero');
eq(I.sortDefense(rows,'alpha').map(r=>r.type),[...types].sort((a,b)=>a.localeCompare(b,'es')));
eq(I.sortDefense(rows,'type').map(r=>r.type),types);
eq(I.sortDefense(rows,'__proto__').map(r=>r.type),types,'Un orden desconocido conserva el de la tabla');

// --- Markup: chart rows, member lists, escaping and the untouched table.
const ctx={TypeAnalysis:A,TeamInsights:I};vm.createContext(ctx);loadShared(ctx);
vm.runInContext(slice('app/analysis-view.js','function multiplier(',"\nfor(const id of ['analysis-defense'"),ctx);
const html=ctx.defenseChart(team,types,chart,true,'type');
eq((html.match(/<details class="fx-row">/g)||[]).length,18,'Una barra por tipo');
ok(html.includes('Débiles 1 · Resisten 0 · Inmunes 0 · Neutrales 4'),'Recuentos generales de Roca');
ok(/fx-seg fx-x4" style="flex-grow:1" title="Muy débiles \(×4 o más\): 1">1</.test(html));
ok(html.includes('Volca <small>4×</small>'),'Integrantes que ocasionan la debilidad');
ok(html.includes('Skarm <small>0×</small>'),'Integrantes inmunes');
ok(/aria-label="Roca\. Débiles 1/.test(html),'Resumen accesible por tipo');
ok(ctx.defenseChart(team,types,chart,false,'type').includes('sin habilidades'));
const sorted=ctx.defenseChart(team,types,chart,true,'weak');
const firstType=sorted.match(/<strong class="fx-type">([^<]+)</)[1];
eq(firstType,weak[0].type,'El gráfico respeta el orden elegido');
const hostile='<img src=x onerror=alert(1)>';
const evil=ctx.defenseChart([mon(hostile,['Agua'])],[hostile,...types],chart,true,'alpha');
ok(!evil.includes('<img'),'Nombres y tipos remotos no se interpretan como HTML');
const table=ctx.defenseTable(team,types,chart,true,false);
ok(table.includes('<caption>Efectividad defensiva</caption>')&&table.includes('<th>Débiles</th>'),'La tabla detallada sigue existiendo');
const bodyTypes=markup=>[...markup.split('<tbody>')[1].matchAll(/<tr><th>([^<]+)<\/th>/g)].map(m=>m[1]);
eq(bodyTypes(table),types,'Tabla sin orden: igual que antes');
eq(bodyTypes(ctx.defenseTable(team,types,chart,true,true,'weak')),weak.map(r=>r.type),'La tabla admite el mismo orden');

// --- Wiring: controls exist, script order, static route and theme colours.
const page=read('index.html'),css=read('style.css'),view=read('app/analysis-view.js');
for(const id of ['analysis-display','analysis-sort','analysis-defense','analysis-abilities'])ok(page.includes(`id="${id}"`),id);
ok(page.indexOf('src="/analysis.js"')<page.indexOf('src="/insights.js"')&&page.indexOf('src="/insights.js"')<page.indexOf('src="/app/helpers.js"'));
ok(fs.readFileSync(path.join(__dirname,'../tracker/api/static.py'),'utf8').includes("'/insights.js': ('web/insights.js'"));
ok(/'analysis-display','analysis-sort'/.test(view),'Los controles nuevos repintan el análisis');
for(const key of I.BUCKETS)ok(css.includes('.fx-'+key+'{'),'Estilo de '+key);
ok(/\[data-theme="light"\]\{--fx-neutral/.test(css),'Tema claro');
ok(!/chart\[|rate\(/.test(fs.readFileSync(path.join(__dirname,'../web/insights.js'),'utf8')),'insights.js no consulta la tabla de tipos por su cuenta');
console.log(checks+' comprobaciones de TeamInsights: OK');
