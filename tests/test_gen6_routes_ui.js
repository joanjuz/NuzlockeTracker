'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const script=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
const xy=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/Routes_XY.json'),'utf8')).routes;
const oras=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/Routes_ORAS.json'),'utf8')).routes;
class Node{
 constructor(){this.children=[];this.value='';this.innerHTML='';this.textContent='';this.dataset={}}
 replaceChildren(){this.children=[]}
 append(item){this.children.push(item)}
}
const nodes={};const $=id=>nodes[id]??=new Node();
const pokemon=(version,ec,route)=>({
 origin_version:version,encryption_constant:ec,species_id:25,
 species:'Pikachu',nickname:'Chispa',met_location_id:route,
 met_location:'Ruta',egg_location_id:0,checksum_valid:true
});
const xyMon=pokemon(24,151,8),yMon=pokemon(25,152,8),
      orasMon=pokemon(26,153,204),asMon=pokemon(27,154,204);
const ctx={
 state:{game:'Pokémon X 1.0',party:[xyMon,yMon,null,null,null,null],
 boxes:{},progress:{deaths:{},origins:{},route_marks:{},encounters:{},traded_routes:[],missed_routes:[]}},
 routeCatalog:xy,placeSignature:'',companionView:false,$,
 normalize:s=>String(s||'').toLowerCase(),esc:s=>String(s||''),
 pokemonKey:p=>String(p.origin_version)+':'+String(p.encryption_constant),
 isDead:()=>false,sprite:()=>'<span class="sprite">PK6</span>',
 document:{createElement:()=>new Node()}
};
vm.createContext(ctx);
const start=script.indexOf('const ORIGIN_TYPES=');
const end=script.indexOf("\n$('route-search').oninput",start);
assert.ok(start>=0&&end>start);
vm.runInContext(script.slice(start,end),ctx);
ctx.renderPlaces();
let out=$('places').children[0].innerHTML;
assert.match(out,/Ruta 1/);
assert.match(out,/data-route-death="24:151"/);
assert.match(out,/data-route-death="25:152"/);
assert.match(out,/data-route-miss="8"/);
assert.match(out,/route-tile occupied/);
assert.doesNotMatch(out,/data-route-death="26:153"/);
assert.equal($('places-count').textContent,'1 / 80 zonas con historial');

ctx.state.game='Omega Ruby 1.0';ctx.state.party=[orasMon,asMon,null,null,null,null];ctx.routeCatalog=oras;ctx.placeSignature='';
ctx.renderPlaces();
out=$('places').children[0].innerHTML;
assert.match(out,/Ruta 101/);
assert.match(out,/data-route-death="26:153"/);
assert.match(out,/data-route-death="27:154"/);
assert.match(out,/data-route-miss="204"/);
assert.doesNotMatch(out,/data-route-death="24:151"/);
assert.equal($('places-count').textContent,'1 / 92 zonas con historial');
assert.match(script,/const versions=/);
assert.match(script,/versions\.flatMap/);
assert.match(script,/versions\.some/);
assert.doesNotMatch(html,/id="refresh-boxes"/);
assert.doesNotMatch(script,/refresh-boxes/);
console.log('Kalos/Hoenn: rutas PK6, tarjetas, marcas, histórico y ocultación de escaneo manual');
