'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../web/companion.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
const styles=fs.readFileSync(path.join(__dirname,'../web/companion.css'),'utf8');
for(const id of ['soullink-pokemon-icon','soullink-sprite-fallback',
                 'soullink-candidate','soullink-choice-row','soullink-notice-error'])
 assert.ok(html.includes('id="'+id+'"'),id);
assert.match(styles,/background:var\(--surface\)/);
assert.match(styles,/color:var\(--accent\)/);
const elements={};
function node(id=''){
  return elements[id]??=(id?{
    id,hidden:true,checked:false,value:'',textContent:'',disabled:false,
    options:[],style:{},replaceChildren(){this.options=[];this.value='';},
    append(option){this.options.push(option);},
    removeAttribute(name){if(name==='src')this.src='';},
    showModal(){this.open=true},close(){this.open=false}
  }:{
    value:'',textContent:'',hidden:false
  });
}
const pokemon=(species,id,nick,route=15,extra={})=>({
 species_id:species,species:nick,nickname:nick,
 origin_version:33,encryption_constant:id,met_location_id:route,
 checksum_valid:true,egg:false,...extra
});
const first=pokemon(25,101,'Chispa'),second=pokemon(133,202,'Eevee'),
 other=pokemon(94,303,'Fantasma',99),dead=pokemon(150,999,'Thor');
const own={party:[first,second,null,null,null,null],
 boxes:{'1':[first,other,...Array(28).fill(null)]},
 progress:{deaths:{}},connection:{status:'connected'},stale:false};
const partnerState={schema_version:1,game:'Ultra Moon 1.0',
 party:[null,null,null,null,null,null],boxes:{},
 progress:{deaths:{},missed_routes:[]}};
const status={configured:true,worker_url:'https://partner.workers.dev',
 my_name:'Local',partner:{name:'HOT RIDER',game:'Ultra Moon 1.0',
 updated_at:12345,state:partnerState}};
let poll;const posted=[];
const ctx={
 console,token:'test-local',localState:own,routeCatalog:[],
 localStorage:{getItem:key=>key==='soullink-manual-enabled'?'true':null,setItem:()=>{}},
 document:{getElementById:node,createElement:()=>node(),querySelectorAll:()=>[]},
 window:{setCompanionView:()=>{}},
 setInterval:fn=>{poll=fn;return 1},
 navigator:{clipboard:{writeText:async()=>{}}},
 confirm:()=>true,
 fetch:async(url,opts)=>{
   if(url==='/api/command'){
     posted.push(JSON.parse(opts.body));return {ok:true,json:async()=>({ok:true})};
   }
   return {ok:true,json:async()=>status};
 },
};
async function settle(){await new Promise(resolve=>setImmediate(resolve));}
(async()=>{
 vm.createContext(ctx);
 vm.runInContext(source,ctx,{filename:'companion.js'});
 await settle();
 const notice=node('soullink-notification');
 assert.equal(notice.hidden,true,'Historical remote deaths stay silent');
 partnerState.progress.deaths['remote-1']={pokemon:dead,recorded_at:'2026-10-09'};
 await poll();await settle();
 assert.equal(notice.hidden,false,'New death opens notice');
 const choice=node('soullink-candidate'),kill=node('soullink-kill');
 assert.equal(node('soullink-choice-row').hidden,false,'Multiple catches require choice');
 assert.equal(choice.options.length,3,'Placeholder and exactly two unique candidates');
 assert.equal(choice.options[1].value,'33:101');
 assert.equal(choice.options[2].value,'33:202');
 assert.equal(kill.disabled,true,'No default first-Pokémon death');
 assert.equal(node('soullink-pokemon-icon').src,'/sprites/150.png',
              'Shows remote Pokémon before selection');
 assert.equal(node('soullink-sprite-fallback').hidden,false);
 assert.equal(posted.length,0,'No automatic deaths');
 choice.value='33:202';choice.onchange();
 assert.equal(kill.disabled,false);
 assert.equal(node('soullink-pokemon-icon').src,'/sprites/133.png');
 node('soullink-pokemon-icon').onload();
 assert.equal(node('soullink-sprite-fallback').hidden,true);
 assert.equal(node('soullink-pokemon-icon').hidden,false);
 await kill.onclick();await settle();
 assert.equal(posted.length,1);
 assert.equal(posted[0].key,'33:202','Marked the explicitly selected second Pokémon');
 assert.equal(notice.hidden,true);
 own.progress.deaths['33:202']={};
 partnerState.progress.deaths['remote-2']={pokemon:dead,recorded_at:'2026-10-10'};
 await poll();await settle();
 assert.equal(notice.hidden,false);
 assert.equal(node('soullink-choice-row').hidden,true,'One eligible Pokémon needs no selector');
 assert.equal(kill.disabled,false);
 assert.match(node('soullink-description').textContent,/Chispa/);
 assert.equal(node('soullink-pokemon-icon').src,'/sprites/25.png');
 node('soullink-pokemon-icon').onerror();
 assert.equal(node('soullink-sprite-fallback').hidden,false);
 node('soullink-dismiss').onclick();
 assert.equal(notice.hidden,true);
 await poll();await settle();
 assert.equal(notice.hidden,true,'Ignore remains ignored');
 console.log('Soul Link: selección de ruta, sprite/fallback y muerte manual OK');
})().catch(error=>{console.error(error);process.exitCode=1});
