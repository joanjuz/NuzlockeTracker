'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const read=file=>fs.readFileSync(path.join(__dirname,'../web',file),'utf8');
const source=read('overlay.js').replace('  poll();',
  '  globalThis.overlayTest={appearance,draw};');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.style={setProperty(){}};this.attributes={};}
  append(child){this.children.push(child);}
  replaceChildren(){this.children=[];}
  setAttribute(name,value){this.attributes[name]=value;}
  removeAttribute(name){delete this.attributes[name];}
}
function harness(query='?layer=counter'){
  const root=new Element('main');
  const context={location:{search:query},URLSearchParams,setInterval(){},
    document:{getElementById:id=>id==='overlay'?root:null,createElement:tag=>new Element(tag),
      documentElement:{style:{setProperty(){}}}}};
  vm.createContext(context);vm.runInContext(source,context);
  const config={order:['sprites','names','hp'],direction:'row',font:'Arial',
    counter_mode:'lives',counter_total:10,counter_lost:'gray',counter_custom_icon:true,
    counter_icon_size:36,counter_icon_version:'v1'};
  const update=(changes={},deaths=0)=>{
    Object.assign(config,changes);context.overlayTest.appearance({...config});
    context.overlayTest.draw({party:[],death_count:deaths});
  };
  update();
  return {root,update,counter:()=>root.children.find(el=>el.dataset.layer==='counter')};
}
function modes_replace_each_other(){
  const h=harness();
  h.update({counter_mode:'deaths'},3);
  assert.equal(h.counter().children.length,1);
  assert.equal(h.counter().children[0].textContent,'Muertes: 3');
  h.update({counter_mode:'lives'},3);
  assert.equal(h.counter().children[0].textContent,'Vidas: 7');
  assert(!h.counter().children.some(el=>String(el.textContent).includes('Muertes')));
  h.update({counter_mode:'off'},3);
  assert.equal(h.counter().hidden,true);assert.equal(h.counter().children.length,0);
}
function ten_custom_icons_turn_gray_then_hide(){
  const h=harness();
  assert.equal(h.counter().children.length,11);
  h.update({},3);
  const icons=h.counter().children.slice(1);
  assert.equal(icons.length,10);
  assert.equal(icons.filter(el=>el.className.includes('lost')).length,3);
  assert(icons.every(el=>el.tag==='img'&&el.src==='/overlay/counter-icon.png?v=v1'));
  h.update({counter_lost:'hide'},3);
  assert.equal(h.counter().children.length,8);
  assert(h.counter().children.slice(1).every(el=>!el.className.includes('lost')));
  h.update({counter_custom_icon:false,counter_icon_version:'v2'},3);
  assert(h.counter().children.slice(1).every(el=>el.tag==='span'&&el.textContent==='♥'));
}
function exhaustion_and_revival(){
  const h=harness();
  for(const deaths of [9,10,11]){
    h.update({counter_lost:'hide'},deaths);
    assert.equal(h.counter().children[0].textContent,'Vidas: '+Math.max(0,10-deaths));
    assert.equal(h.counter().children.length,1+Math.max(0,10-deaths));
  }
  h.update({},8);
  assert.equal(h.counter().children[0].textContent,'Vidas: 2');
  assert.equal(h.counter().children.length,3);
}
function independent_and_composed_layers(){
  const independent=harness('?layer=counter&slot=2');
  assert.equal(independent.root.children.length,1);
  assert.equal(independent.counter().children.length,11);
  const composed=harness('?layer=all');
  assert.deepEqual(composed.root.children.map(el=>el.dataset.layer),['sprites','names','hp']);
  composed.update({counter_in_composition:true});
  assert.deepEqual(composed.root.children.map(el=>el.dataset.layer),['sprites','names','hp','counter']);
  composed.update({counter_in_composition:false});
  assert.equal(composed.root.children.length,3);
  const hp=harness('?layer=hp');hp.update({counter_in_composition:true});
  assert.deepEqual(hp.root.children.map(el=>el.dataset.layer),['hp']);
}
function editor_counter_controls_and_links(){
  const markup=read('overlay-editor.html'),editor=read('overlay-editor.js');
  new vm.Script(editor);
  for(const field of ['counter_mode','counter_total','counter_lost','counter_icon_size',
    'counter_custom_icon','counter_in_composition','counter_icon_upload'])
    assert(markup.includes(`id="${field}"`),field);
  assert(editor.includes("['Muertes / vidas','counter']"));
  assert(editor.includes("post('/api/overlay/counter-icon'"));
}
for(const test of [modes_replace_each_other,ten_custom_icons_turn_gray_then_hide,
  exhaustion_and_revival,independent_and_composed_layers,editor_counter_controls_and_links]){
  test();console.log('PASS '+test.name);
}
