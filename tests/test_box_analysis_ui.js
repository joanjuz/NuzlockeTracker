'use strict';
// Boxes · analysis view: entries, filters, sorting and the read-only table.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const I=require('../web/insights.js');
const {loadShared,slice,read}=require('./ui_shared.js');
let checks=0;const ok=(value,message)=>{assert.ok(value,message);checks++};const eq=(a,b,message)=>{assert.deepEqual(a,b,message);checks++};
const stats=(HP,ATK,DEF,SPA,SPD,SPE)=>({HP,ATK,DEF,SPA,SPD,SPE});
let ec=100;
const mon=(nickname,species,types,ability,base,extra={})=>({species_id:25,species,nickname,types,ability,ability_id:1,nature:'Firme',level:null,stats:null,
  move_names:['Placaje','—','—','—'],encryption_constant:ec++,origin_version:33,base_stats:base,...extra});
const pika=mon('Chispa','Pikachu',['Eléctrico'],'Estática',stats(35,55,40,50,50,90));
const chari=mon('Llama','Charizard',['Fuego','Volador'],'Mar Llamas',stats(78,84,78,109,85,100));
const gyara=mon('Ola','Gyarados',['Agua','Volador'],'Intimidación',stats(95,125,79,60,100,81));
const mystery=mon('Duda','MissingNo',['Normal'],'Estática',null);
const partial=mon('Medio','Parcial',['Roca'],'Robustez',{HP:50,ATK:60});
const egg=mon('Huevo','Togepi',['Hada'],'Dicha',stats(35,20,65,40,65,20),{egg:true});
const lead=mon('Líder','Garchomp',['Dragón','Tierra'],'Piel Tosca',stats(108,130,95,80,85,102),{level:62,max_hp:210,stats:{ATQ:190,DEF:140,VEL:150,ATE:110,DEE:120}});
const box=n=>Array(30).fill(null);
const boxes={'1':box(),'2':box(),'10':box()};
boxes['1'][0]=pika;boxes['1'][4]=chari;boxes['2'][2]=gyara;boxes['2'][3]=mystery;boxes['10'][29]=partial;boxes['10'][0]=egg;
const snapshot={game:'Ultra Moon 1.0',party:[lead,null,null,null,null,null],boxes,box_verified:true,stale:false,scan:{active:false,completed:0},
  progress:{deaths:{[I.pokemonId(gyara)]:{pokemon:gyara}}},connection:{status:'connected'}};

// --- Pure helpers.
eq(I.bst(pika),320);eq(I.bst(chari),534);
eq(I.bst(mystery),null,'Sin datos importados no hay BST');
eq(I.bst(partial),null,'Un registro parcial no inventa el total');
eq(I.baseStat(partial,'HP'),50);eq(I.baseStat(partial,'SPE'),null);
eq(I.baseStat({base_stats:{HP:'80'}},'HP'),null,'Solo números');
eq(I.baseStat({base_stats:{ATQ:190}},'ATK'),null,'Las estadísticas actuales no son estadísticas base');
eq(I.pokemonId({}),null);
const entries=I.ownedEntries(snapshot);
eq(entries.map(e=>e.key),['box:1:0','box:1:4','box:2:2','box:2:3','box:10:0','box:10:29'],'Cajas en orden numérico, solo espacios ocupados');
eq(entries.find(e=>e.pokemon===gyara).dead,true);eq(entries.find(e=>e.pokemon===egg).egg,true);
eq(I.ownedEntries(snapshot,{party:true})[0].key,'party:0');
eq(I.ownedEntries({boxes:null}).length,0);eq(I.ownedEntries(null).length,0);
const names=list=>list.map(e=>e.pokemon.nickname);
eq(names(I.filterEntries(entries,{type:'Volador'})),['Llama','Ola'],'Tipo primario o secundario');
eq(names(I.filterEntries(entries,{ability:'Estática'})),['Chispa','Duda']);
eq(names(I.filterEntries(entries,{available:true})),['Chispa','Llama','Duda','Medio'],'Disponibles: ni muertos ni huevos');
eq(names(I.filterEntries(entries,{query:'  GYARA '})),['Ola'],'Busca por especie');
eq(names(I.filterEntries(entries,{query:'intimidacion'})),['Ola'],'Conserva búsqueda por habilidad');
eq(names(I.filterEntries(entries,{query:'placaje'})),['Chispa','Llama','Ola','Duda','Huevo','Medio'],'Conserva búsqueda por movimiento');
eq(names(I.filterEntries([{...entries[0],pokemon:{...pika,item:'Restos',met_location:'Ruta 12'}}],{query:'restos ruta 12'})),['Chispa'],'Conserva objeto y origen');
eq(names(I.filterEntries(entries,{query:'lider'})),[],'El equipo no está si no se pide');
eq(names(I.filterEntries(I.ownedEntries(snapshot,{party:true}),{query:'lider'})),['Líder'],'Sin tildes ni mayúsculas');
eq(names(I.filterEntries(entries,{box:2})),['Ola','Duda']);
eq(names(I.filterEntries(entries,{})),names(entries));
eq(names(I.sortEntries(entries,'bst','desc')),['Ola','Llama','Chispa','Huevo','Duda','Medio'],'Sin BST al final');
eq(names(I.sortEntries(entries,'bst','asc')),['Huevo','Chispa','Llama','Ola','Duda','Medio'],'Sin BST al final también en ascendente');
eq(names(I.sortEntries(entries,'SPE','desc')).slice(0,3),['Llama','Chispa','Ola']);
eq(names(I.sortEntries(entries,'HP','desc')).slice(0,4),['Ola','Llama','Medio','Chispa'],'Un dato parcial ordena por lo que sí tiene');
eq(names(I.sortEntries(entries,'name','asc')),['Chispa','Duda','Huevo','Llama','Medio','Ola']);
eq(names(I.sortEntries(entries,'type','asc'))[0],'Ola');
eq(names(I.sortEntries(I.ownedEntries(snapshot,{party:true}),'level','desc'))[0],'Líder','El nivel solo se conoce en el equipo');
eq(names(I.sortEntries(entries,'level','desc')),names(entries),'Sin nivel se conserva el orden de almacenamiento');
eq(names(I.sortEntries(entries,'constructor','desc')),names(entries));
eq(I.entryFacets(entries),{types:['Agua','Eléctrico','Fuego','Hada','Normal','Roca','Volador'],abilities:['Dicha','Estática','Intimidación','Mar Llamas','Robustez']});

// --- View in a fake DOM.
class El{
  constructor(){Object.assign(this,{children:[],options:[],innerHTML:'',textContent:'',value:'',hidden:false,checked:false,listeners:{},dataset:{}})}
  replaceChildren(){this.children=[];this.options=[]}
  append(x){this.children.push(x)}
  add(o){this.options.push(o)}
  addEventListener(type,fn){this.listeners[type]=fn}
}
const nodes={};const $=id=>nodes[id]??=new El();
const opened=[],commands=[];
const ctx={$,TeamInsights:I,state:snapshot,companionView:false,boxSignature:'',console,
  Option:function(text,value){this.text=text;this.value=String(value)},
  setText:(node,text)=>{node.textContent=text},
  sprite:p=>'<i>'+p.species+'</i>',openDetail:(p,key)=>opened.push([p&&p.nickname,key]),
  command:c=>commands.push(c),document:{createElement:()=>new El()}};
vm.createContext(ctx);loadShared(ctx);
vm.runInContext(slice('app/helpers.js','function normalize(','\n'),ctx);
vm.runInContext(slice('app/boxes.js','function nationalDexLimit(',"\n$('box').onchange"),ctx);
vm.runInContext(read('app/box-analysis.js'),ctx);
$('box').value='1';
// Normal view: untouched.
ctx.renderBoxes();
eq($('boxes').hidden,false);eq($('box-analysis').hidden,true);eq($('box-analysis-controls').hidden,true);
eq($('boxes').children.length,2,'Vista normal: los dos Pokémon de la caja 1');
ok($('boxes').children[0].innerHTML.includes('Caja 1 · 1'));
eq($('box-analysis').innerHTML,'','La vista normal no dibuja la tabla');
// Gallery is the first analysis view; individual specimens remain native buttons.
function cardsAreDefaultAndKeepBaseSeparate(){
  $('box-view-mode').value='analysis';$('box-view-mode').onchange();
  const gallery=$('box-analysis').innerHTML;
  ok(gallery.includes('class="box-analysis-gallery"'),'La vista analítica abre tarjetas, no tabla');
  eq((gallery.match(/<article class="box-analysis-card/g)||[]).length,2,'Una tarjeta por ejemplar');
  ok(gallery.includes('data-entry="box:1:4"')&&gallery.includes('type="button"'),'La ficha se abre con botón nativo por teclado');
  ok(gallery.includes('aria-label="Estadísticas base de la especie"'),'Las barras se identifican como base');
  ok(!gallery.includes('<table'),'La tabla no ocupa la vista principal');
}
cardsAreDefaultAndKeepBaseSeparate();
$('box-analysis-presentation').value='table';ctx.renderBoxes();
// Analysis view of the selected box.
$('box-view-mode').value='analysis';$('box-view-mode').onchange();
eq($('boxes').hidden,true);eq($('box-analysis').hidden,false);eq($('box-analysis-controls').hidden,false);
eq($('living-dex-label').hidden,true);
let html=$('box-analysis').innerHTML;
const rowNames=markup=>[...markup.matchAll(/<strong>([^<]+)<\/strong>/g)].map(m=>m[1]);
eq(rowNames(html),['Llama','Chispa'],'Caja 1 por BST descendente');
ok(html.includes('<td class="box-bst">534</td>'));
ok(html.includes('Caja 1 · 5')&&html.includes('Caja 1 · 1'),'Caja y posición original');
ok(html.includes('Fuego / Volador')&&html.includes('Mar Llamas')&&html.includes('Firme')&&html.includes('Placaje'));
ok(/<td><span class="box-stat-missing">No disponible<\/span><\/td>/.test(html),'Nivel no disponible en cajas');
ok(!html.includes('actual'.concat(' ')+'190'),'En cajas no hay estadísticas actuales');
eq($('box-analysis-status').textContent,'2 Pokémon · 3 / 32 cajas leídas · faltan cajas por leer: el resultado es parcial');
eq($('box-analysis-type').options.map(o=>o.value),['','Agua','Eléctrico','Fuego','Hada','Normal','Roca','Volador']);
// All read boxes, with missing base stats shown as such.
$('global').checked=true;ctx.renderBoxes();html=$('box-analysis').innerHTML;
eq(rowNames(html),['Ola','Llama','Chispa','Huevo','Duda','Medio']);
ok(html.includes('<td colspan="7" class="box-stat-missing">Estadísticas base: No disponible</td>'),'Sin datos: no se inventan');
ok(/<td>50<\/td><td>60<\/td><td><span class="box-stat-missing">No disponible<\/span><\/td>/.test(html),'Registro parcial');
ok(html.includes('<span class="box-badge">Muerto</span>')&&html.includes('<span class="box-badge">Huevo</span>'));
// Filters and sorting.
$('box-analysis-available').checked=true;ctx.renderBoxes();
eq(rowNames($('box-analysis').innerHTML),['Llama','Chispa','Duda','Medio']);
$('box-analysis-type').value='Volador';ctx.renderBoxes();
eq(rowNames($('box-analysis').innerHTML),['Llama']);
$('box-analysis-type').value='';$('box-analysis-available').checked=false;$('search').value='gyara';ctx.renderBoxes();
eq(rowNames($('box-analysis').innerHTML),['Ola']);
$('search').value='zzz';ctx.renderBoxes();
ok($('box-analysis').innerHTML.includes('Ningún Pokémon coincide'));
$('search').value='';$('box-analysis-sort').value='name';$('box-analysis-sort').onchange();
eq($('box-analysis-direction').value,'asc','Los nombres empiezan de la A a la Z');
eq(rowNames($('box-analysis').innerHTML),['Chispa','Duda','Huevo','Llama','Medio','Ola']);
// Party rows keep base and current values apart.
$('box-analysis-party').checked=true;$('box-analysis-sort').value='level';$('box-analysis-sort').onchange();
html=$('box-analysis').innerHTML;
eq(rowNames(html)[0],'Líder');
ok(html.includes('<td>62</td>')&&html.includes('Equipo · 1'));
ok(html.includes('<td>108<small class="box-current-stat">actual 210</small></td>'),'PS base y PS actuales, separados');
ok(html.includes('<td>130<small class="box-current-stat">actual 190</small></td>'));
ok(html.includes('<td class="box-bst">600</td>'),'BST es la suma de las base, no de las actuales');
// Same frame again: nothing is rebuilt.
$('box-analysis').innerHTML='sentinel';ctx.renderBoxes();
eq($('box-analysis').innerHTML,'sentinel','Sin cambios no se vuelve a dibujar');
// Opening a row shows the detail; no command is ever sent.
const click=key=>$('box-analysis').listeners.click({target:{closest:()=>({dataset:{entry:key}})}});
click('box:2:2');click('party:0');
eq(opened,[['Ola','box:2:2'],['Líder','party:0']]);
$('box-analysis').listeners.click({target:{closest:()=>null}});
eq(commands.length,0,'La vista de análisis no envía órdenes');
// Untrusted names stay inert; missing base stats everywhere are explained.
const hostile='<img src=x onerror=alert(1)>';
ctx.state={...snapshot,party:[],boxes:{'1':[mon(hostile,hostile,[hostile],hostile,null,{move_names:[hostile]})]},box_verified:false};
ctx.companionView=true;$('box-analysis-sort').value='bst';ctx.renderBoxes();
ok(!$('box-analysis').innerHTML.includes('<img src=x'),'Datos del compañero escapados');
ok($('box-analysis-status').textContent.includes('cajas no verificadas')&&$('box-analysis-status').textContent.includes('cajas del compañero'));
ok($('box-analysis-status').textContent.includes('sin estadísticas base'));
// Large PCs: the table is capped and says so.
ctx.companionView=false;
const full=Object.fromEntries(Array.from({length:32},(_,b)=>[String(b+1),Array.from({length:30},(_,i)=>mon('N'+b+'_'+i,'Pikachu',['Eléctrico'],'Estática',stats(35,55,40,50,50,90)))]));
$('box-analysis-party').checked=false;ctx.state={...snapshot,boxes:full,progress:{}};ctx.renderBoxes();
eq(($('box-analysis').innerHTML.match(/<tr class=/g)||[]).length,240);
ok($('box-analysis').innerHTML.includes('Se muestran 240 de 960'));
eq($('box-analysis-status').textContent,'960 Pokémon · 32 / 32 cajas leídas');
// A key for every box is not proof that all thirty slots have been read.
ctx.state={...snapshot,boxes:Object.fromEntries(Array.from({length:32},(_,i)=>[String(i+1),[pika]]))};ctx.renderBoxes();
ok($('box-analysis-status').textContent.includes('0 / 32 cajas leídas')&&$('box-analysis-status').textContent.includes('resultado es parcial'),'Un escaneo con registros incompletos no afirma PC completo');
// Back to the normal view.
ctx.state=snapshot;$('global').checked=false;$('box-view-mode').value='normal';$('box-view-mode').onchange();
eq($('boxes').hidden,false);eq($('box-analysis').hidden,true);eq($('living-dex-label').hidden,false);
eq($('boxes').children.length,2,'La vista normal vuelve intacta');

function cardOrderingAndProvenanceAreEffective(){
  ctx.state={...snapshot,party:[{...lead,base_stats_source:'Definitive Game Data · partida actual'}]};
  $('box-analysis-party').checked=true;$('global').checked=true;
  $('box-analysis-presentation').value='cards';$('box-view-mode').value='analysis';$('box-view-mode').onchange();
  const cards=()=>[...$('box-analysis').innerHTML.matchAll(/class="box-card-name">([^<]+)</g)].map(match=>match[1]);
  $('box-analysis-sort').value='bst';$('box-analysis-sort').onchange();
  eq(cards(),['Líder','Ola','Llama','Chispa','Huevo','Duda','Medio'],'Orden BST aplicado a las tarjetas dibujadas');
  $('box-analysis-direction').value='asc';$('box-analysis-direction').onchange();
  eq(cards(),['Huevo','Chispa','Llama','Ola','Líder','Duda','Medio'],'Sentido ascendente cambia realmente el orden');
  const gallery=$('box-analysis').innerHTML;
  ok(gallery.includes('title="Definitive Game Data · partida actual"'),'La procedencia completa es consultable');
  ok(gallery.includes('Estadísticas actuales')&&gallery.includes('210'),'Se conservan actuales disponibles en detalle separado');
  ok(gallery.includes('Naturaleza')&&gallery.includes('Firme'),'Naturaleza se muestra sin cambiar las bases');
  eq(ctx.boxCurrentStat(ctx.state.party[0],'HP'),210,'No se modifican los actuales del snapshot');
}
cardOrderingAndProvenanceAreEffective();

function megaPreviewIsSortedWithoutMutatingSnapshot(){
  let active=false;
  const normal={...pika,base_stats_source:'Referencia Gen7',mega_preview:{label:'Mega de prueba'}};
  ctx.analysisPokemon=p=>active&&p.encryption_constant===normal.encryption_constant?{...p,base_stats:stats(100,150,100,150,100,100),stats:null,max_hp:null,types:['Dragón'],analysis_mega:true,analysis_preview_label:'Mega de prueba'}:p;
  ctx.analysisMegaControl=p=>p.mega_preview?'<button type="button" data-analysis-mega="33:100">Aplicar mega</button>':'';
  ctx.state={...snapshot,party:[],boxes:{'1':[normal,chari]}};
  $('box-analysis-party').checked=false;$('box-analysis-sort').value='bst';$('box-analysis-sort').onchange();
  const names=()=>[...$('box-analysis').innerHTML.matchAll(/class="box-card-name">([^<]+)</g)].map(match=>match[1]);
  eq(names(),['Llama','Chispa']);
  active=true;ctx.renderBoxes();
  eq(names(),['Chispa','Llama'],'Ordena según la forma mega explícitamente aplicada');
  ok($('box-analysis').innerHTML.includes('Mega de prueba')&&$('box-analysis').innerHTML.includes('data-analysis-mega='),'Forma simulada y control visibles');
  eq(normal.base_stats.HP,35,'La simulación no reescribe las bases originales');
  $('box-analysis-type').value='Dragón';ctx.renderBoxes();eq(names(),['Chispa'],'El filtro usa los tipos de la simulación');
  ctx.analysisPokemon=p=>p;ctx.analysisMegaControl=()=>'';$('box-analysis-type').value='';
}
megaPreviewIsSortedWithoutMutatingSnapshot();

// --- Wiring.
const page=read('index.html'),css=read('style.css'),source=read('app/box-analysis.js');
for(const id of ['box-view-mode','box-analysis-controls','box-analysis-type','box-analysis-ability','box-analysis-sort','box-analysis-direction','box-analysis-available','box-analysis-party','box-analysis-status','box-analysis','living-dex-label','living-dex-sprites-label'])
  ok(page.includes(`id="${id}"`),id);
for(const value of ['bst','HP','ATK','DEF','SPA','SPD','SPE','level','type','name'])ok(page.includes(`<option value="${value}">`),'Orden '+value);
ok(page.includes('>Vista normal</option><option value="analysis">Vista de análisis</option>'));
ok(!/command\(/.test(source),'box-analysis.js no envía órdenes al servicio');
ok(css.includes('.box-analysis-table')&&css.includes('.box-stat-missing'));
console.log(checks+' comprobaciones de análisis de cajas: OK');
