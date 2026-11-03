'use strict';
// Ejecuta overlay.js real: capa «Cementerio» de OBS.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../web/overlay.js'),'utf8');
const css=fs.readFileSync(path.join(__dirname,'../web/overlay.css'),'utf8');

class Element {
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.attributes={};this.className='';
    this.style={setProperty(){}};this.classList={toggle(){},contains(){return false;}};}
  append(child){this.children.push(child);}
  addEventListener(type,fn){(this.listeners??={})[type]=fn;}
  fire(type){this.listeners?.[type]?.();}
  replaceChildren(){this.children=[];}
  setAttribute(n,v){this.attributes[n]=v;}
  removeAttribute(n){delete this.attributes[n];}
  get firstElementChild(){return this.children[0]||null;}
  get lastElementChild(){return this.children[this.children.length-1]||null;}
}
function harness(){
  const root=new Element('main'),timers=[];
  const context={location:{search:'?layer=graveyard'},URLSearchParams,setTimeout(fn){timers.push(fn);},
    fetch:async()=>{throw new Error('sin red');},
    document:{getElementById:id=>id==='overlay'?root:null,createElement:tag=>new Element(tag),
      documentElement:{clientWidth:1280,style:{setProperty(){}}}}};
  vm.createContext(context);
  vm.runInContext(source.replace(/\r?\n  poll\(\);\r?\n/,'\n  globalThis.overlayTest={appearance,draw};\n'),context);
  const config={order:['sprites','names','hp'],direction:'row',font:'Arial',slot_width:142,hp_border_width:1,
    hp_label:'none',counter_mode:'off',graveyard_max:3,graveyard_columns:3,graveyard_sprite_size:64,
    graveyard_order:'recent',graveyard_title:true,graveyard_show_name:true,graveyard_show_species:false,
    graveyard_show_level:true,graveyard_show_route:true};
  context.overlayTest.appearance({...config});
  const group=()=>root.children.find(el=>el.className==='overlay-graveyard');
  return {root,timers,context,config,group,
    apply(changes){Object.assign(config,changes);context.overlayTest.appearance({...config});}};
}
const grave=(i,extra={})=>({n:i,species_id:25,nickname:'Caído'+i,species:'Pikachu',level:10+i,route:'Ruta '+i,
  image_rev:('abc'+i).padEnd(12,'0'),...extra});
const state=(list,total=list.length)=>({party:[],death_count:99,graveyard:list,graveyard_total:total});
const cards=h=>h.group().children.find(el=>el.className==='grave-grid').children;
const texts=card=>card.children.filter(el=>el.tag==='span').map(el=>el.textContent);

function shows_newest_first_with_limit_title_and_fields(){
  const h=harness();
  h.context.overlayTest.draw(state([grave(0),grave(1),grave(2),grave(3)],7));
  assert.equal(h.group().children[0].textContent,'Cementerio · 7');
  assert.equal(cards(h).length,3);
  assert.deepEqual(texts(cards(h)[0]),['Caído0','Nv. 10','Ruta 0']);
  const img=cards(h)[0].children[0];
  assert.equal(img.src,'/overlay/graveyard/abc000000000');
  assert.equal(img.alt,'');
}
function server_order_is_kept_and_optional_fields(){
  // The server sorts (recent/oldest) over ALL deaths; the client only trims.
  const h=harness();h.apply({graveyard_order:'oldest',graveyard_show_level:false,graveyard_show_route:false,
    graveyard_show_species:true,graveyard_title:false});
  h.context.overlayTest.draw(state([grave(4),grave(3),grave(2),grave(1),grave(0)]));
  assert.equal(h.group().children[0].className,'grave-grid','sin título');
  assert.deepEqual(cards(h).map(c=>texts(c)[0]),['Caído4','Caído3','Caído2']);
  assert.deepEqual(texts(cards(h)[0]),['Caído4','Pikachu']);
}
function switching_sprite_set_reloads_images(){
  const h=harness();
  h.context.overlayTest.draw(state([grave(0)]));
  const before=cards(h)[0].children[0];
  h.apply({sprite_set:'HD Pixel'});
  h.context.overlayTest.draw(state([grave(0)]));
  const after=cards(h)[0].children[0];
  assert.notEqual(after,before,'se reconstruye al cambiar de conjunto');
  assert.equal(after.src,'/overlay/graveyard/abc000000000?set=HD%20Pixel');
  after.fire('error');h.timers.shift()();
  assert.equal(after.src,'/overlay/graveyard/abc000000000?set=HD%20Pixel&retry=1');
}
function no_rebuild_when_unchanged_and_text_is_never_html(){
  const h=harness();
  const list=[grave(0,{nickname:'<img src=x onerror=alert(1)>'})];
  h.context.overlayTest.draw(state(list));
  const first=cards(h)[0];
  h.context.overlayTest.draw(state(list));
  assert.equal(cards(h)[0],first,'misma tarjeta: sin parpadeo');
  assert.equal(texts(first)[0],'<img src=x onerror=alert(1)>');
  assert.equal(first.innerHTML,undefined);
}
function missing_sprite_is_retried_then_shown(){
  const h=harness();
  h.context.overlayTest.draw(state([grave(0)]));
  const img=cards(h)[0].children[0];
  img.fire('error');
  assert.equal(img.style.visibility,'hidden');
  assert.equal(h.timers.length,1);
  h.timers.shift()();
  assert.equal(img.src,'/overlay/graveyard/abc000000000?retry=1');
  img.fire('load');
  assert.equal(img.style.visibility,'visible');
}
function empty_graveyard_and_css(){
  const h=harness();
  h.context.overlayTest.draw(state([]));
  assert.equal(cards(h).length,0);
  assert.match(css,/\.grave-sprite\{[^}]*filter:grayscale\(1\)/);
  assert.match(css,/grid-template-columns:repeat\(var\(--grave-cols,6\),max\(var\(--slot\),var\(--grave-sprite/);
}
for(const test of [shows_newest_first_with_limit_title_and_fields,server_order_is_kept_and_optional_fields,
  no_rebuild_when_unchanged_and_text_is_never_html,switching_sprite_set_reloads_images,missing_sprite_is_retried_then_shown,empty_graveyard_and_css]){
  test();console.log('PASS',test.name);
}
