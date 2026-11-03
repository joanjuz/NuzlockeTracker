'use strict';
// Tracker UI: shared helpers, sprite fallback and shared state. Load order lives in index.html.
// Shared helpers (companion.js uses them too). Partner snapshots are untrusted.
const $=id=>document.getElementById(id);
const esc=value=>String(value??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=value=>{const n=typeof value==='number'?value:typeof value==='string'&&value.trim()?Number(value):NaN;return Number.isFinite(n)?String(n):'—'};
const list=value=>Array.isArray(value)?value:[];
const GAME_FAMILIES=Object.freeze({'Pokémon X 1.0':'xy','Pokémon Y 1.0':'xy','Omega Ruby 1.0':'oras','Alpha Sapphire 1.0':'oras','Ultra Sun 1.0':'usum','Ultra Moon 1.0':'usum'});
const GEN6_GAMES=Object.freeze(Object.keys(GAME_FAMILIES).filter(game=>GAME_FAMILIES[game]!=='usum'));
const gameFamily=game=>Object.prototype.hasOwnProperty.call(GAME_FAMILIES,game)?GAME_FAMILIES[game]:null;
const spriteId=value=>{const n=Number(value);return Number.isInteger(n)&&n>0?n:0};
// End shared helpers.
async function getJSON(url,options){
  const response=await fetch(url,options);
  if(!response.ok)throw Error('Respuesta '+response.status+' de '+url);
  return response.json();
}
// One delegated fallback for every sprite: local file -> PokeAPI -> number (or Poké Ball).
const SPRITE_REMOTE='https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/';
function spriteFallback(event){
  const img=event.target;
  if(!img||img.tagName!=='IMG'||!img.dataset)return;
  // Item icons have no fallback chain: a missing icon just disappears, the item name stays.
  if(img.dataset.itemIcon!==undefined){img.hidden=true;return;}
  if(img.dataset.fallback===undefined)return;
  const id=Number(img.dataset.fallback);
  if(!img.dataset.remote&&Number.isInteger(id)&&id>0){img.dataset.remote='1';img.src=SPRITE_REMOTE+id+'.png';return;}
  if(img.dataset.fallbackDone)return;
  img.dataset.fallbackDone='1';
  if(img.dataset.fallbackFinal==='ball'){img.src='/app-icon.png';img.classList.add('living-dex-ball');return;}
  img.hidden=true;const next=img.nextElementSibling;if(next)next.hidden=false;
}
document.addEventListener('error',spriteFallback,true);
// Live regions announce only real changes, not every websocket frame.
function setText(node,text){if(node.textContent!==text)node.textContent=text}
function normalize(v){return String(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase()}
// Shared UI state. Classic scripts share these top-level bindings in load order.
let routeGame='';
let state=null,localState=null,companionView=false,token=null,selected=null,boxSignature='',socket,miniSignature='',placeSignature='',detailSignature='',routeCatalog=[],detailPokemon=null,moveRequest=0,analysisData=null,analysisSignature='',analysisTeamSignature='',deadSignature='';
