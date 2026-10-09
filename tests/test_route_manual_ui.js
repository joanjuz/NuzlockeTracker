'use strict';
// Regression: death belongs to the chosen Pokemon, never to the partner automatically.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const src = fs.readFileSync(require('node:path').join(__dirname, '../web/app.js'), 'utf8');
const html = fs.readFileSync(require('node:path').join(__dirname, '../web/index.html'), 'utf8');
assert.doesNotMatch(html, /Lectura automática de 32 cajas/);
const start = src.indexOf('const ORIGIN_TYPES=');
const end = src.indexOf("\n$('route-search').oninput", start);
assert.ok(start >= 0 && end > start, 'routePokemon y renderPlaces deben existir');

class Node {
  constructor() { this.children=[]; this.innerHTML='';this.textContent='';this.events={};this.dataset={}; }
  replaceChildren(){this.children=[]}
  append(child){this.children.push(child)}
  addEventListener(type,cb){this.events[type]=cb}
}
const nodes={};
const get = id => nodes[id] ??= new Node();
const mon={origin_version:33,encryption_constant:12,species_id:448,species:'Lucario',nickname:'Goty',met_location_id:8,met_location:'Ruta 1',checksum_valid:true,egg_location_id:0};
const ctx={
  state:{party:[mon,null,null,null,null,null],boxes:{},progress:{deaths:{},missed_routes:[]}},
  routeCatalog:[{id:8,name:'Ruta 1',ids:[8]}],
  companionView:false,
  placeSignature:'',
  $:get,
  esc:s=>String(s),
  normalize:s=>String(s).toLowerCase(),
  pokemonKey:p=>String(p.origin_version)+':'+String(p.encryption_constant),
  isDead:p=>Boolean(ctx.state.progress.deaths[ctx.pokemonKey(p)]),
  sprite:p=>'<span class="dummy-sprite">'+p.nickname+'</span>',
  document:{createElement:()=>new Node()},
  command:cmd=>{calls.push(cmd);return Promise.resolve()},
  confirm:()=>{throw new Error('No debe pedir confirmación para marcar muerte')},
};
const calls=[];
vm.createContext(ctx);
vm.runInContext(src.slice(start,end),ctx);
ctx.renderPlaces();
assert.match(get('places').children[0].innerHTML, /data-route-death="33:12"/);
assert.match(get('places').children[0].innerHTML, />Muerte<\/button>/);
assert.doesNotMatch(get('places').children[0].innerHTML, /☠/);
assert.match(get('places').children[0].innerHTML, /Goty/);
// Dos especies de una misma ruta: la categoría manda, nunca la especie.
const fossil={...mon,encryption_constant:66,nickname:'Restos fósiles',species_id:94};
const gift={...mon,encryption_constant:67,nickname:'Regalito',species_id:25};
const egg={...mon,encryption_constant:68,nickname:'Criado',species_id:133,egg_location_id:30001};
ctx.state.boxes={'1':[fossil,gift,egg]};
ctx.state.progress.origins={'33:66':'fossil','33:67':'gift'};
ctx.placeSignature='';
ctx.renderPlaces();
assert.equal(get('places').children.length,4,'Ruta + Fósil + Regalo + Huevo');
assert.match(get('places').children[0].innerHTML, /Goty/);
assert.match(get('places').children[0].innerHTML,/Restos fósiles/,'La ruta conserva una huella Fósil');
assert.doesNotMatch(get('places').children[0].innerHTML,/Regalito|Criado/);
assert.match(get('places').children[1].innerHTML,/Fósiles/);
assert.match(get('places').children[1].innerHTML,/Restos fósiles/);
assert.match(get('places').children[2].innerHTML,/Regalos/);
assert.match(get('places').children[3].innerHTML,/Huevos/);
assert.match(get('places').children[3].innerHTML,/Criado/);
assert.match(get('places').children[1].innerHTML,/Ruta 1/,'Preserva lugar de encuentro');
const changeStart=src.indexOf("$('places').addEventListener('change'");
const eventStart=src.indexOf("$('places').addEventListener('click'");
const eventEnd=src.indexOf("\n$('detail-content')",eventStart);
assert.ok(eventStart>=0&&eventEnd>eventStart);
vm.runInContext(src.slice(changeStart,eventEnd),ctx);
const change={target:{closest:selector=>selector==='[data-origin-key]'?
 {dataset:{originKey:'33:66'},value:'trade',disabled:false}:null}};
get('places').events.change(change);
assert.deepEqual(JSON.parse(JSON.stringify(calls[0])),{action:'set_origin',key:'33:66',category:'trade'});
const click={target:{closest:selector=>selector==='[data-route-death]'?{dataset:{routeDeath:'33:12'}}:null}};
get('places').events.click(click);
assert.deepEqual(JSON.parse(JSON.stringify(calls[1])),{action:'mark_dead',key:'33:12'});
ctx.state.progress.deaths={'33:12':{pokemon:mon}};
ctx.placeSignature='';
ctx.renderPlaces();
assert.doesNotMatch(get('places').children[0].innerHTML,/data-route-death/);
assert.match(get('places').children[0].innerHTML,/Muerto/);
ctx.state.progress.deaths={};
ctx.companionView=true;
ctx.placeSignature='';
ctx.renderPlaces();
assert.doesNotMatch(get('places').children[0].innerHTML,/data-route-death/);
assert.match(get('places').children[0].innerHTML,/Solo lectura/);
get('places').events.click(click);
assert.equal(calls.length,2, 'Nunca editar manualmente la partida del compañero');
// Cuando el Pokémon desaparece, la ruta mantiene su historial sin asumir intercambio.
ctx.companionView=false;
ctx.state.party=[null,null,null,null,null,null];
ctx.state.boxes={};
ctx.state.progress.origins={};
ctx.state.progress.route_marks={};
ctx.state.progress.encounters={'33:12':{...mon}};
ctx.state.progress.deaths={};
ctx.placeSignature='';
ctx.renderPlaces();
let route=get('places').children[0].innerHTML;
assert.match(route,/Ya no está en las lecturas/);
assert.match(route,/data-route-mark="33:12" data-kind="trade"/);
assert.doesNotMatch(route,/Intercambiado<\/small>/,'No deducir intercambios solo por desaparecer');
const tradeClick={target:{closest:selector=>selector==='[data-route-mark]'?
 {dataset:{routeMark:'33:12',kind:'trade'}}:null}};
get('places').events.click(tradeClick);
assert.deepEqual(JSON.parse(JSON.stringify(calls[2])),
 {action:'mark_route',key:'33:12',kind:'trade'});
// Una vez confirmado el intercambio, el estado de la ruta sigue visible.
ctx.state.progress.route_marks={'33:12':{kind:'trade',pokemon:mon}};
ctx.placeSignature='';
ctx.renderPlaces();
route=get('places').children[0].innerHTML;
assert.match(route,/Intercambiado/);
assert.match(route,/Goty/);
assert.doesNotMatch(route,/empty-pokemon/);
assert.match(get('places-count').textContent,/zonas con historial/);
const undoClick={target:{closest:selector=>selector==='[data-route-undo]'?
 {dataset:{routeUndo:'33:12'}}:null}};
get('places').events.click(undoClick);
assert.deepEqual(JSON.parse(JSON.stringify(calls[3])),
 {action:'clear_route_mark',key:'33:12'});
// La acción Fósil es un botón; crea una huella y sección sin hardcodear especie.
ctx.state.party=[fossil,null,null,null,null,null];
ctx.state.progress.origins={};
ctx.state.progress.encounters={'33:66':{...fossil}};
ctx.state.progress.route_marks={};
ctx.placeSignature='';
ctx.renderPlaces();
route=get('places').children[0].innerHTML;
assert.match(route,/data-route-mark="33:66" data-kind="fossil"/);
const fossilClick={target:{closest:selector=>selector==='[data-route-mark]'?
 {dataset:{routeMark:'33:66',kind:'fossil'}}:null}};
get('places').events.click(fossilClick);
assert.deepEqual(JSON.parse(JSON.stringify(calls[4])),
 {action:'mark_route',key:'33:66',kind:'fossil'});
ctx.state.progress.origins={'33:66':'fossil'};
ctx.state.progress.route_marks={'33:66':{kind:'fossil',pokemon:fossil}};
ctx.placeSignature='';
ctx.renderPlaces();
assert.match(get('places').children[0].innerHTML,/Fósil/);
assert.match(get('places').children[1].innerHTML,/Fósiles/);
ctx.companionView=true;
ctx.placeSignature='';
ctx.renderPlaces();
assert.doesNotMatch(get('places').children[0].innerHTML,/data-route-undo|data-route-mark/);

console.log('Rutas: historial, intercambio confirmado, botón Fósil, deshacer y solo lectura OK');
