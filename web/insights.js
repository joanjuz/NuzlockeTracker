/* Team insights: counts and explanations built on TypeAnalysis (web/analysis.js).
   No matchup rule lives here: every multiplier comes from TypeAnalysis. */
(function(root){
'use strict';
const TA=root.TypeAnalysis||(typeof require==='function'?require('./analysis.js'):null);
const arr=value=>Array.isArray(value)?value:[];
// Display name used in every explanation; snapshots may lack a nickname.
const label=p=>String((p&&(p.nickname||p.species))||'Pokémon');
// Bucket order is the drawing order of the bars: worst matchup first.
const BUCKETS=['x4','x2','neutral','half','quarter','immune'];
function bucketOf(value){return value===0?'immune':value>=4?'x4':value>1?'x2':value===1?'neutral':value<=.25?'quarter':'half'}
// One row per attacking type with the members in each effectiveness bucket.
function defenseSummary(chart,types,team,abilities=true){
  return arr(types).map((type,index)=>{
    const row={type,index,x4:[],x2:[],neutral:[],half:[],quarter:[],immune:[]};
    for(const p of arr(team)){
      if(!p)continue;
      const value=TA.defensive(chart,type,p,abilities);
      row[bucketOf(value)].push({pokemon:p,value});
    }
    row.weak=row.x4.length+row.x2.length;
    row.resist=row.half.length+row.quarter.length;
    row.immunities=row.immune.length;
    row.neutrals=row.neutral.length;
    row.total=row.weak+row.resist+row.immunities+row.neutrals;
    return row;
  });
}
// Stable orderings; ties always fall back to the chart order of the types.
function sortDefense(rows,order){
  const orders={
    weak:(a,b)=>b.weak-a.weak||b.x4.length-a.x4.length||(a.resist+a.immunities)-(b.resist+b.immunities),
    resist:(a,b)=>(b.resist+b.immunities)-(a.resist+a.immunities)||b.immunities-a.immunities||b.quarter.length-a.quarter.length||a.weak-b.weak,
    alpha:(a,b)=>String(a.type).localeCompare(String(b.type),'es')
  };
  const by=Object.prototype.hasOwnProperty.call(orders,order)?orders[order]:null;
  const sorted=arr(rows).slice();
  if(by)sorted.sort((a,b)=>by(a,b)||a.index-b.index);
  return sorted;
}
// --- Owned Pokémon: flat entries from the party and the boxes that were actually read.
const STAT_KEYS=['HP','ATK','DEF','SPA','SPD','SPE'];
const fold=value=>String(value??'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
// Same identity the tracker uses for deaths: it survives evolution, renaming and moving.
function pokemonId(p){return p&&Number.isInteger(p.encryption_constant)?`${p.origin_version??33}:${p.encryption_constant}`:null}
// A base stat is a number only when the imported data has it; never a guess.
function baseStat(p,key){
  const stats=p&&p.base_stats;
  if(!stats||typeof stats!=='object'||!Object.prototype.hasOwnProperty.call(stats,key))return null;
  const value=stats[key];
  return typeof value==='number'&&Number.isFinite(value)&&value>0?value:null;
}
// BST needs the six base stats; a partial record has no total.
function bst(p){
  let total=0;
  for(const key of STAT_KEYS){const value=baseStat(p,key);if(value===null)return null;total+=value}
  return total;
}
function ownedEntries(snapshot,options={}){
  const entries=[],deaths=snapshot&&snapshot.progress&&snapshot.progress.deaths||{};
  const push=(pokemon,origin)=>{
    const id=pokemonId(pokemon);
    entries.push({pokemon,id,...origin,dead:id!==null&&Object.prototype.hasOwnProperty.call(deaths,id),egg:pokemon.egg===true});
  };
  if(options.party)arr(snapshot&&snapshot.party).forEach((p,slot)=>{if(p&&typeof p==='object')push(p,{kind:'party',box:0,slot,key:`party:${slot}`})});
  if(options.boxes!==false){
    const boxes=snapshot&&snapshot.boxes&&typeof snapshot.boxes==='object'?snapshot.boxes:{};
    for(const box of Object.keys(boxes).sort((a,b)=>Number(a)-Number(b)))
      arr(boxes[box]).forEach((p,slot)=>{if(p&&typeof p==='object')push(p,{kind:'box',box:Number(box),slot,key:`box:${box}:${slot}`})});
  }
  return entries;
}
// Every filter is optional; an empty filter keeps everything.
function filterEntries(entries,filters={}){
  const words=fold(filters.query).trim().split(/\s+/).filter(Boolean);
  const type=filters.type||'',ability=filters.ability||'',box=Number(filters.box)||0;
  return arr(entries).filter(entry=>{
    const p=entry.pokemon;
    if(type&&!arr(p.types).includes(type))return false;
    if(ability&&String(p.ability??'')!==ability)return false;
    if(filters.available&&(entry.dead||entry.egg))return false;
    if(box&&entry.kind==='box'&&entry.box!==box)return false;
    if(words.length){const text=fold([p.nickname,p.species].join(' '));if(!words.every(word=>text.includes(word)))return false}
    return true;
  });
}
const SORT_TEXT={name:p=>fold(label(p)),type:p=>arr(p.types).map(fold).join(' ')};
function sortValue(p,key){
  if(key==='bst')return bst(p);
  if(STAT_KEYS.includes(key))return baseStat(p,key);
  if(key==='level')return Number.isInteger(p.level)?p.level:null;
  return Object.prototype.hasOwnProperty.call(SORT_TEXT,key)?SORT_TEXT[key](p)||null:null;
}
// Unknown values always go last, in both directions; ties keep the storage order.
function sortEntries(entries,key,direction='desc'){
  const sign=direction==='asc'?1:-1;
  return arr(entries).map((entry,index)=>({entry,index,value:sortValue(entry.pokemon,key)})).sort((a,b)=>{
    if(a.value===null||b.value===null)return (a.value===null)-(b.value===null)||a.index-b.index;
    const order=typeof a.value==='string'?a.value.localeCompare(b.value,'es'):a.value-b.value;
    return sign*order||a.index-b.index;
  }).map(item=>item.entry);
}
// Options for the type and ability filters, from the Pokémon that exist.
function entryFacets(entries){
  const types=new Set(),abilities=new Set();
  for(const entry of arr(entries)){
    for(const type of arr(entry.pokemon.types))if(typeof type==='string'&&type)types.add(type);
    const ability=entry.pokemon.ability;if(typeof ability==='string'&&ability&&ability!=='—')abilities.add(ability);
  }
  const sorted=set=>[...set].sort((a,b)=>a.localeCompare(b,'es'));
  return {types:sorted(types),abilities:sorted(abilities)};
}
const api={BUCKETS,bucketOf,label,defenseSummary,sortDefense,STAT_KEYS,pokemonId,baseStat,bst,ownedEntries,filterEntries,sortEntries,sortValue,entryFacets};
root.TeamInsights=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
