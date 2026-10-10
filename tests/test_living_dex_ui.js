'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
const css=fs.readFileSync(path.join(__dirname,'../web/style.css'),'utf8');
const begin=src.indexOf('function normalize(');
const end=src.indexOf('\nfunction render(next)',begin);
assert.ok(begin>0&&end>begin);
class Node{
 constructor(tag){this.tag=tag;this.children=[];this.innerHTML='';this.textContent='';this.checked=false;this.value='';this.hidden=false}
 replaceChildren(){this.children=[]}
 append(x){this.children.push(x)}
}
const nodes={};const $=id=>nodes[id]??=new Node('div');
const opened=[];
const ctx={$,
  state:null,boxSignature:'',
  esc:x=>String(x??''),
  sprite:p=>'<span class="real-sprite">'+p.species+'</span>',
  openDetail:(p,key)=>opened.push([p.species_id,key]),
  document:{createElement:tag=>new Node(tag)}
};
vm.createContext(ctx);
vm.runInContext(src.slice(begin,end),ctx);
const mon=(id,name)=>({species_id:id,species:name,nickname:name,
 ability:'Estática',item:'—',met_location:'Ruta',move_names:[]});
const boxes=n=>Object.fromEntries(Array.from({length:n},(_,i)=>[String(i+1),Array(30).fill(null)]));
let gen6=boxes(31);
gen6['1'][0]=mon(25,'Pikachu');
gen6['2'][3]=mon(25,'Pikachu');
gen6['31'][29]=mon(721,'Volcanion');
const game='Pokémon X 1.0';
ctx.state={game,box_verified:true,boxes:gen6,progress:{}};
$('box').value='1';$('search').value='';$('living-dex').checked=true;
ctx.renderBoxes();
assert.equal($('boxes').className,'box-grid living-dex-grid');
assert.equal($('boxes').children.length,721);
assert.match($('living-dex-status').textContent,/2 \/ 721 especies/);
let missing=$('boxes').children[0];
assert.equal(missing.className,'box-pokemon living-dex-missing');
assert.match(missing.innerHTML,/<img class="living-dex-ball" src="\/app-icon.png"/);
assert.match(missing.innerHTML,/#001/);
assert.doesNotMatch(missing.innerHTML,/Caja 1/);
const pika=$('boxes').children[24];
assert.match(pika.innerHTML,/#025/);
assert.match(pika.innerHTML,/×2/,'Las especies repetidas ocupan una casilla');
assert.doesNotMatch(pika.innerHTML,/Caja 1/,'No mostrar posición de almacenamiento en Living Dex');
pika.onclick();
assert.deepEqual(opened.pop(),[25,'box:1:0']);
assert.match($('boxes').children[720].innerHTML,/#721/);
assert.match($('boxes').children[720].innerHTML,/Volcanion/);
$('search').value='025';ctx.boxSignature='';ctx.renderBoxes();
assert.equal($('boxes').children.length,1);
assert.match($('boxes').children[0].innerHTML,/#025/);
$('search').value='';ctx.boxSignature='';ctx.state.box_verified=false;
ctx.renderBoxes();
assert.equal($('boxes').children.length,1);
assert.match($('boxes').children[0].textContent,/Esperando el escaneo automático completo/);
assert.doesNotMatch($('boxes').children[0].innerHTML,/living-dex-ball/);
ctx.state.box_verified=true;delete gen6['31'];ctx.boxSignature='';
ctx.renderBoxes();
assert.equal($('boxes').children.length,1,'Una caja sin leer no marca 721 especies como ausentes');
gen6['31']=Array(30).fill(null);ctx.boxSignature='';
$('living-dex').checked=false;ctx.renderBoxes();
assert.equal($('boxes').className,'box-grid');
assert.equal($('boxes').children.length,1);
assert.match($('boxes').children[0].innerHTML,/Caja 1 · 1/,'Vista de cajas normal intacta');
assert.equal($('living-dex-status').hidden,true);
let gen7=boxes(32);gen7['32'][0]=mon(807,'Zeraora');gen7['1'][0]=mon(808,'No disponible');
ctx.state={game:'Ultra Moon 1.0',boxes:gen7,box_verified:true,progress:{}};
ctx.boxSignature='';$('living-dex').checked=true;ctx.renderBoxes();
assert.equal($('boxes').children.length,807);
assert.match($('living-dex-status').textContent,/1 \/ 807 especies/);
assert.match($('boxes').children[806].innerHTML,/#807/);
assert.doesNotMatch($('boxes').children[806].innerHTML,/Caja 32/);
assert.doesNotMatch($('boxes').children[0].innerHTML,/No disponible/);
assert.match(html,/id="living-dex"/);
assert.match(html,/id="living-dex-status"/);
assert.match(css,/filter:grayscale\(1\)/);
assert.match(css,/\.living-dex-grid/);
console.log('Living Dex: Gen6 721, Gen7 807, sin falso vacío, Pokémon duplicados y vuelta a vista normal OK');
