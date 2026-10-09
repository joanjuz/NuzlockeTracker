// Exercise the real history renderer and revive callback without a browser.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(require('path').join(__dirname,'../web/app.js'),'utf8');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.innerHTML=''}
 append(...items){this.children.push(...items)}
 replaceChildren(){this.children=[]}
 setAttribute(name,value){this.attributes[name]=value}
}
const nodes={},calls=[],$=id=>nodes[id]??=new Element('div');
const pokemon={origin_version:33,encryption_constant:12,species_id:1,species:'Bulbasaur',nickname:'Brote'};
const ctx={$,confirm:()=>false,document:{createElement:tag=>new Element(tag)},state:{progress:{deaths:{'33:12':{pokemon}}}},deadSignature:'',esc:s=>String(s??''),openDetail:()=>calls.push('detail'),command:async cmd=>calls.push(cmd)};
vm.createContext(ctx);
for(const name of ['pokemonKey','isDead','renderDead','sprite']){
 const start=source.indexOf('function '+name+'('),end=source.indexOf('\nfunction ',start+1);
 vm.runInContext(source.slice(start,end),ctx);
}
(async()=>{
 ctx.renderDead();const entry=$('dead').children[0];
 assert.equal(entry.tag,'article');assert.equal(entry.children.length,2);
 const [detail,revive]=entry.children;assert(detail.innerHTML.includes('dead-sprite'));assert.equal(revive.textContent,'Revivir');
 await revive.onclick();assert.equal(calls.length,1);assert.equal(calls[0].action,'revive');assert.equal(calls[0].key,'33:12');assert.equal(calls[0].decrement_counter,false);assert.equal(revive.disabled,false);
 ctx.state.progress.deaths={};ctx.renderDead();assert.equal($('dead-count').textContent,0);assert($('dead').innerHTML.includes('Sin muertes'));
 assert(!ctx.sprite(pokemon).includes('dead-sprite'));
 console.log('Revivir: botón independiente, comando y retirada del estado gris OK');
})().catch(e=>{console.error(e);process.exitCode=1});
