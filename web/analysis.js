/* Gen7 type matchups; layout and partitioning inspired by wavebeem/pkmn.help. */
(function(root){
'use strict';
// Types come from untrusted snapshots too: only own numeric chart entries count.
const own=(o,k)=>o!==null&&typeof o==='object'&&Object.prototype.hasOwnProperty.call(o,k);
function rate(chart,attack,t){const v=own(chart,attack)&&own(chart[attack],t)?chart[attack][t]:1;return typeof v==='number'&&Number.isFinite(v)?v:1}
const typeList=value=>Array.isArray(value)?[...new Set(value)]:[];
function basic(chart,attack,defense){return typeList(defense).reduce((n,t)=>n*rate(chart,attack,t),1)}
function defensive(chart,attack,p,abilities=true){let n=basic(chart,attack,p.types||[]);if(!abilities)return n;const id=p.ability_id;
const immunities={10:'Eléctrico',11:'Agua',18:'Fuego',26:'Tierra',31:'Eléctrico',78:'Eléctrico',114:'Agua',157:'Planta'};
if(immunities[id]===attack)n=0;
if(id===87){if(attack==='Agua')n=0;if(attack==='Fuego')n*=1.25}
if((id===85||id===199)&&attack==='Fuego')n*=.5;
if(id===47&&['Fuego','Hielo'].includes(attack))n*=.5;
if(id===218&&attack==='Fuego')n*=2;
if([111,116,232].includes(id)&&n>1)n*=.75;
if(id===25&&n<=1)n=0;
return n}
function attackType(move,p,abilities=true){if(!abilities||move.type!=='Normal')return move.type;return {174:'Hielo',182:'Hada',184:'Volador',206:'Eléctrico'}[p.ability_id]||move.type}
function offensive(chart,move,p,defense,abilities=true){
  const attack=attackType(move,p,abilities);
  let n=1;
  for(const t of typeList(defense)){
    let x=rate(chart,attack,t);
    // Scrappy (113): Normal and Fighting moves hit Ghost.
    if(abilities&&p.ability_id===113&&t==='Fantasma'&&['Normal','Lucha'].includes(attack))x=1;
    // Freeze-Dry (573) is super effective against Water.
    if(move.id===573&&t==='Agua'&&attack==='Hielo')x=2;
    // Thousand Arrows (614) hits Flying.
    if(move.id===614&&t==='Volador'&&attack==='Tierra')x=1;
    n*=x;
  }
  // Flying Press (560) adds the Flying matchup.
  if(move.id===560)n*=basic(chart,'Volador',defense);
  return n;
}
function coverage(chart,pokemon,defense,abilities=true){
  let best=null;
  for(const p of pokemon){
    const moves=Array.isArray(p.analysis_moves)?p.analysis_moves:[];
    for(const move of moves){
      if(!move||move.category==='Estado')continue;
      const value=offensive(chart,move,p,defense,abilities);
      if(best===null||value>best.value)best={value,move,pokemon:p};
    }
  }
  return best;
}
const api={basic,defensive,attackType,offensive,coverage};root.TypeAnalysis=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
