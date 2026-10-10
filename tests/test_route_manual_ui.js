'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs'),vm = require('node:vm'),path = require('node:path');
const src = fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const html = fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
const start = src.indexOf('const ORIGIN_TYPES='),end = src.indexOf("\n$('route-search').oninput", start);
assert.ok(start>=0 && end>start);
class Node{
 constructor(){this.children=[];this.innerHTML='';this.textContent='';this.events={};this.dataset={}}
 replaceChildren(){this.children=[]}
 append(value){this.children.push(value)}
 addEventListener(name,handler){this.events[name]=handler}
}
const nodes={};const get=id=>nodes[id]??=new Node();
const mon=(id,name,route=8,extra={})=>({
  origin_version:33,encryption_constant:id,species_id:448,species:'Lucario',nickname:name,
  met_location_id:route,met_location:'Ruta 1',egg_location_id:0,checksum_valid:true,...extra
});
const goty=mon(12,'Goty'),fossil=mon(66,'Fosilito',8,{species_id:94}),gift=mon(67,'Regalo',8),egg=mon(68,'Criado',8,{egg_location_id:30001});
const calls=[];
const ctx={
 state:{party:[goty,null,null,null,null,null],boxes:{},progress:{deaths:{},origins:{},route_marks:{},encounters:{},traded_routes:[],missed_routes:[]}},
 routeCatalog:[{id:8,name:'Ruta 1',ids:[8]},{id:9,name:'Ruta 2',ids:[9]}],
 companionView:false,placeSignature:'',$:get,
 esc:s=>String(s),normalize:s=>String(s).toLowerCase(),
 pokemonKey:p=>String(p.origin_version)+':'+String(p.encryption_constant),
 isDead:p=>Boolean(ctx.state.progress.deaths[ctx.pokemonKey(p)]),
 sprite:p=>'<span class="dummy-sprite">'+p.nickname+'</span>',
 document:{createElement:()=>new Node()},
 command:cmd=>{calls.push(cmd);return Promise.resolve()},
 confirm:()=>{throw Error('Nunca pedir confirmación por Muerte')}
};
vm.createContext(ctx);
vm.runInContext(src.slice(start,end),ctx);
const clickStart=src.indexOf("$('places').addEventListener('click'");
const clickEnd=src.indexOf("\n$('detail-content')",clickStart);
assert.ok(clickStart>=0&&clickEnd>clickStart);
vm.runInContext(src.slice(clickStart,clickEnd),ctx);
const click=(selector,data,pressed)=>get('places').events.click({target:{closest:s=>s===selector?{
 dataset:data,getAttribute:()=>pressed?'true':'false'
}:null}});
ctx.renderPlaces();
let routes=get('places').children[0].innerHTML;
assert.match(routes,/data-route-death="33:12"/);
assert.match(routes,/data-route-mark="33:12" data-kind="fossil"/);
assert.match(routes,/<fieldset class="route-tile occupied"/,'Una ruta es un recuadro único');
assert.match(routes,/<legend class="route-legend">Ruta 1<\/legend>/,'Nombre de ruta integrado en el borde');
assert.doesNotMatch(routes,/<h4>|class="route-footprint-name"/,'No mostrar nombres bajo los sprites');
assert.doesNotMatch(routes,/<select|data-origin-key/,'Sin menús desplegables');
assert.doesNotMatch(routes,/data-kind="trade"/,'Sin botón de intercambio por Pokémon');
assert.match(routes,/data-route-trade="9"/,'Intercambiado en ruta vacía');
assert.doesNotMatch(routes,/data-route-trade="8"/,'No ofrecer botón en una ruta ocupada');
assert.ok(routes.indexOf('data-route-trade="9"')>routes.indexOf('data-route-miss="9"'),'Botón Intercambiado bajo MISS');
click('[data-route-death]',{routeDeath:'33:12'});
assert.deepEqual(JSON.parse(JSON.stringify(calls.pop())),{action:'mark_dead',key:'33:12'});
click('[data-route-mark]',{routeMark:'33:12',kind:'fossil'});
assert.deepEqual(JSON.parse(JSON.stringify(calls.pop())),{action:'mark_route',key:'33:12',kind:'fossil'});
click('[data-route-trade]',{routeTrade:'9'},false);
assert.deepEqual(JSON.parse(JSON.stringify(calls.pop())),{action:'route_trade',route:'9',traded:true});
ctx.state.progress.traded_routes=['9'];
ctx.placeSignature='';ctx.renderPlaces();
routes=get('places').children[0].innerHTML;
assert.match(routes,/↔ Intercambiado/);
assert.match(routes,/↶ Quitar intercambio/);
click('[data-route-trade]',{routeTrade:'9'},true);
assert.deepEqual(JSON.parse(JSON.stringify(calls.pop())),{action:'route_trade',route:'9',traded:false});
// El escaneo incompleto solo conserva histórico, sin suponer que hay intercambio.
ctx.state.party=[null,null,null,null,null,null];
ctx.state.progress.traded_routes=[];
ctx.state.progress.encounters={'33:12':{...goty}};
ctx.placeSignature='';ctx.renderPlaces();
routes=get('places').children[0].innerHTML;
assert.match(routes,/Ya no está en las lecturas/);
assert.match(routes,/data-route-trade="8"/);
assert.doesNotMatch(routes,/Intercambiado<\/small>/,'No presumir intercambio por ausencia');
assert.doesNotMatch(routes,/data-kind="trade"/);
ctx.state.progress.route_marks={'33:12':{kind:'trade',source:'auto',pokemon:goty}};
ctx.placeSignature='';ctx.renderPlaces();
routes=get('places').children[0].innerHTML;
assert.match(routes,/Intercambiado/);
assert.match(routes,/Goty/);
assert.doesNotMatch(routes,/data-route-trade="8"/,'Ruta auto-marcada no necesita botón manual');
// Fósil conserva huella de ruta original y sección separada.
ctx.state.party=[fossil,null,null,null,null,null];
ctx.state.progress.origins={'33:66':'fossil'};
ctx.state.progress.route_marks={'33:66':{kind:'fossil',pokemon:fossil}};
ctx.state.progress.encounters={'33:66':{...fossil}};
ctx.placeSignature='';ctx.renderPlaces();
assert.match(get('places').children[0].innerHTML,/Fosilito/);
assert.match(get('places').children[1].innerHTML,/Fósiles/);
assert.match(get('places').children[1].innerHTML,/<legend class="route-legend">Ruta 1<\/legend>/);
assert.doesNotMatch(get('places').children[1].innerHTML,/<h4>|origin-type-label/,
 'Sin mote ni etiqueta Fósil debajo de Deshacer');
assert.match(get('places').children[1].innerHTML,/>Deshacer<\/button><\/div>/,
 'Deshacer termina el bloque del Pokémon sin Fósil repetido');
// Regalos y huevos previamente identificados se respetan sin selector.
ctx.state.boxes={'1':[gift,egg]};
// Dos Pokémon obtenidos en la misma ruta comparten recuadro horizontal.
ctx.state.boxes={'1':[gift,egg,mon(98,'Segundo fósil',8,{species_id:133})]};
ctx.state.progress.origins['33:98']='fossil';
ctx.placeSignature='';ctx.renderPlaces();
const fossilHtml=get('places').children[1].innerHTML;
assert.equal((fossilHtml.match(/<fieldset/g)||[]).length,1,'Un único marco por ruta entre fósiles');
assert.equal((fossilHtml.match(/route-pokemon-entry/g)||[]).length,2,'Dos sprites dentro de la misma ruta');

ctx.state.progress.origins['33:67']='gift';
ctx.placeSignature='';ctx.renderPlaces();
assert.equal(get('places').children.length,4);
assert.doesNotMatch(get('places').children[1].innerHTML,/<select/);
// Todo el perfil del compañero sigue siendo de solo lectura.
ctx.companionView=true;ctx.placeSignature='';ctx.renderPlaces();
routes=get('places').children[0].innerHTML;
assert.doesNotMatch(routes,/data-route-mark|data-route-undo|<select/);
assert.match(routes,/data-route-trade="9" disabled/);
const css=fs.readFileSync(path.join(__dirname,'../web/style.css'),'utf8');
assert.match(css,/\.route-tile \.route-sprites\{[\s\S]*?flex-wrap:wrap/,
 'Los sprites comparten fila y solo saltan cuando falta ancho');
assert.match(css,/\.route-tile \.route-legend\{/,'Leyenda integrada en borde de ruta');
assert.match(css,/\.route-grid\{[\s\S]*?minmax\(min\(100%,310px\),1fr\)/);
console.log('Rutas: marcos por ruta, sprites horizontales, sin motes ni etiquetas repetidas OK');
