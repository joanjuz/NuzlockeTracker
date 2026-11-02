'use strict';
// Ejecuta overlay.js real: objeto equipado, sprite gris al morir y sondeo sin solapes.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const read=file=>fs.readFileSync(path.join(__dirname,'../web',file),'utf8');
const source=read('overlay.js');
const css=read('overlay.css');

class Element {
  constructor(tag){
    this.tag=tag;this.children=[];this.dataset={};this.attributes={};this.className='';
    this.style={setProperty(){}};
    const self=this;
    this.classList={
      toggle(name,on){const set=new Set(self.className.split(' ').filter(Boolean));
        if(on===undefined?!set.has(name):on)set.add(name);else set.delete(name);
        self.className=[...set].join(' ');},
      contains(name){return self.className.split(' ').includes(name);},
    };
  }
  append(child){this.children.push(child);}
  addEventListener(type,fn){(this.listeners??={})[type]=fn;}
  fire(type){this.listeners?.[type]?.();}
  replaceChildren(){this.children=[];}
  setAttribute(name,value){this.attributes[name]=value;}
  removeAttribute(name){delete this.attributes[name];}
  get firstElementChild(){return this.children[0]||null;}
  get lastElementChild(){return this.children[this.children.length-1]||null;}
}

function harness(query){
  const root=new Element('main');
  const timers=[];
  const context={location:{search:query},URLSearchParams,
    setTimeout(fn){timers.push(fn);},setInterval(){throw new Error('setInterval no debe usarse');},
    fetch:async()=>{throw new Error('sin red');},
    document:{getElementById:id=>id==='overlay'?root:null,createElement:tag=>new Element(tag),
      documentElement:{clientWidth:1280,style:{setProperty(){}}}}};
  vm.createContext(context);
  vm.runInContext(source.replace(/\r?\n  poll\(\);\r?\n/,'\n  globalThis.overlayTest={appearance,draw,poll};\n'),context);
  const config={order:['sprites','names','hp'],direction:'row',font:'Arial',slot_width:142,
    hp_border_width:1,hp_label:'none',hp_low_threshold:25,hp_mid_threshold:50,
    counter_mode:'off',items_in_composition:false,item_size:14,item_color:'#f2c15c'};
  return {root,timers,context,config,
    apply(changes={}){Object.assign(config,changes);context.overlayTest.appearance({...config});}};
}
const slot=(n,extra={})=>({slot:n,present:true,species_id:25,nickname:'Chispa',item:'',
  hp:10,max_hp:20,percent:50,dead:false,stale:false,image_rev:'1',image_format:'png',...extra});
const party=(...slots)=>{const all=[1,2,3,4,5,6].map(n=>({slot:n,present:false}));
  for(const s of slots)all[s.slot-1]=s;return {party:all,death_count:0};};
const layerOf=(h,name)=>h.root.children.find(el=>el.dataset.layer===name);

function items_layer_shows_current_item(){
  const h=harness('?layer=items');h.apply();
  h.context.overlayTest.draw(party(slot(1,{item:'Restos'}),slot(2)));
  const group=layerOf(h,'items');
  assert.ok(group,'capa de objetos');
  assert.equal(group.children[0].lastElementChild.textContent,'Restos');
  assert.equal(group.children[1].lastElementChild.textContent,'');
  // Por defecto solo el nombre: no se pide ningún icono.
  assert.equal(group.children[0].firstElementChild.hidden,true);
  assert.equal(group.children[0].firstElementChild.src,undefined);
  // El objeto cambia en vivo cuando el Pokémon lo usa o se lo quitan.
  h.context.overlayTest.draw(party(slot(1,{item:''})));
  assert.equal(group.children[0].lastElementChild.textContent,'');
}
function item_text_is_never_html(){
  const h=harness('?layer=items');h.apply();
  h.context.overlayTest.draw(party(slot(1,{item:'<img src=x onerror=alert(1)>'})));
  const label=layerOf(h,'items').children[0].lastElementChild;
  assert.equal(label.textContent,'<img src=x onerror=alert(1)>');
  assert.equal(label.innerHTML,undefined);
}
function item_icon_modes_and_offline_fallback(){
  const h=harness('?layer=items');h.apply({item_display:'icon'});
  h.context.overlayTest.draw(party(slot(1,{item:'Restos',item_id:234}),slot(2,{item:'',item_id:0})));
  const [first,second]=layerOf(h,'items').children;
  const icon=first.firstElementChild,label=first.lastElementChild;
  assert.equal(icon.src,'/overlay/item/234.png');
  assert.equal(icon.hidden,false);
  assert.equal(label.textContent,'','solo icono');
  assert.equal(second.firstElementChild.hidden,true,'sin objeto no hay icono');
  // Sin conexión o icono inexistente: se oculta y aparece el nombre.
  icon.fire('error');
  h.context.overlayTest.draw(party(slot(1,{item:'Restos',item_id:234})));
  assert.equal(icon.hidden,true);
  assert.equal(label.textContent,'Restos');
  // A minute later the icon is requested again (network may be back).
  icon.dataset.failedAt=String(Date.now()-61000);
  h.context.overlayTest.draw(party(slot(1,{item:'Restos',item_id:234})));
  assert.match(icon.src,/^\/overlay\/item\/234\.png\?retry=\d+$/);
  assert.equal(icon.hidden,false);
  h.apply({item_display:'both'});
  h.context.overlayTest.draw(party(slot(1,{item:'Cinta Elección',item_id:220})));
  assert.equal(icon.src,'/overlay/item/220.png');
  assert.equal(icon.hidden,false);
  assert.equal(label.textContent,'Cinta Elección');
}
function composition_places_items_after_names_only_when_enabled(){
  const h=harness('?layer=all');h.apply();
  assert.deepEqual(h.root.children.map(el=>el.dataset.layer),['sprites','names','hp']);
  h.apply({items_in_composition:true});
  assert.deepEqual(h.root.children.map(el=>el.dataset.layer),['sprites','names','items','hp']);
  h.apply({order:['hp','sprites','names']});
  assert.deepEqual(h.root.children.map(el=>el.dataset.layer),['hp','sprites','names','items']);
}
function dead_pokemon_sprite_turns_gray(){
  const h=harness('?layer=sprites');h.apply();
  h.context.overlayTest.draw(party(slot(1),slot(2,{dead:true,hp:0,percent:0})));
  const slots=layerOf(h,'sprites').children;
  assert.equal(slots[0].classList.contains('dead'),false);
  assert.equal(slots[1].classList.contains('dead'),true);
  // Revivir devuelve el color.
  h.context.overlayTest.draw(party(slot(1),slot(2)));
  assert.equal(slots[1].classList.contains('dead'),false);
  assert.match(css,/\.overlay-slot\.dead \.overlay-image\{filter:grayscale\(1\)/);
}
function shadow_disabled_keeps_gray_filter_valid(){
  // Con la sombra desactivada la variable queda vacía, no 'none'.
  assert.match(source,/sprite_shadow\?'drop-shadow\([^']*\)':''\)/);
  assert.match(css,/grayscale\(1\) var\(--sprite-shadow,\)/);
}
async function polling_never_overlaps(){
  const h=harness('?layer=sprites');
  let inFlight=0,maxInFlight=0;
  h.context.fetch=async url=>{
    inFlight++;maxInFlight=Math.max(maxInFlight,inFlight);
    await new Promise(r=>setImmediate(r));inFlight--;
    return {ok:true,json:async()=>url.includes('settings')?{...h.config}:party(slot(1))};
  };
  await h.context.overlayTest.poll();
  assert.equal(h.timers.length,1,'programa el siguiente sondeo solo al terminar');
  for(let i=0;i<5;i++){const next=h.timers.shift();await next();}
  assert.ok(maxInFlight<=2,'como mucho estado + ajustes a la vez');
}

(async()=>{
  for(const test of [items_layer_shows_current_item,item_text_is_never_html,item_icon_modes_and_offline_fallback,
    composition_places_items_after_names_only_when_enabled,dead_pokemon_sprite_turns_gray,
    shadow_disabled_keeps_gray_filter_valid,polling_never_overlaps]){
    await test();console.log('PASS',test.name);
  }
})().catch(error=>{console.error(error);process.exit(1);});
