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
const api={BUCKETS,bucketOf,label,defenseSummary,sortDefense};
root.TeamInsights=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
