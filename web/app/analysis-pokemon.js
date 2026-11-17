'use strict';
// Presentation-only mega selection. The state read from the emulator is never changed.
let analysisMegaScope='',analysisMegaSelected=new Map();
function analysisMegaContext(){
  const scope=JSON.stringify([typeof state==='undefined'?null:state?.game,typeof companionView==='undefined'?false:companionView]);
  if(scope!==analysisMegaScope){analysisMegaScope=scope;analysisMegaSelected.clear()}
}
function analysisMegaStamp(p){return JSON.stringify([p.species_id,p.analysis_original_form??p.form??0,p.item_id,p.mega_preview?.form,p.mega_preview?.item_id])}
function analysisHasMega(p){
  const mega=p?.mega_preview;
  return Boolean(mega&&typeof mega==='object'&&Number.isInteger(mega.form)&&mega.form>0&&mega.item_id===p.item_id&&TeamInsights.pokemonId(p));
}
function analysisPokemon(p){
  analysisMegaContext();
  if(!analysisHasMega(p)||analysisMegaSelected.get(TeamInsights.pokemonId(p))!==analysisMegaStamp(p))return p;
  const mega=p.mega_preview;
  return {...p,form:mega.form,types:list(mega.types).slice(),ability_id:mega.ability_id,ability:mega.ability,
    base_stats:mega.base_stats,base_stats_source:mega.base_stats_source,sprite_id:mega.sprite_id||p.sprite_id||p.species_id,
    analysis_mega:true,analysis_original_form:p.analysis_original_form??p.form??0,analysis_preview_label:mega.label||'Mega',
    stats:null,hp:null,max_hp:null};
}
function analysisMegaControl(p){
  analysisMegaContext();
  if(!analysisHasMega(p))return '';
  const selected=analysisMegaSelected.get(TeamInsights.pokemonId(p))===analysisMegaStamp(p);
  return `<button type="button" class="analysis-mega-button${selected?' active':''}" data-analysis-mega="${esc(TeamInsights.pokemonId(p))}" aria-pressed="${selected}" title="${esc(p.mega_preview.reference_only?'Simulación con datos de referencia; pueden variar en tu ROM.':'Simulación con datos de esta partida.')}${p.mega_preview.ability_known===false?' Habilidad por confirmar; no se aplican efectos de una habilidad incierta.':''} No cambia el juego.">${selected?'Quitar mega':'Aplicar mega'}</button>`;
}
function analysisToggleMega(id,pokemon){
  analysisMegaContext();
  const available=pokemon||TeamInsights.ownedEntries(typeof state==='undefined'?null:state,{party:true}).map(entry=>entry.pokemon);
  const p=available.find(candidate=>TeamInsights.pokemonId(candidate)===id);
  if(!analysisHasMega(p))return false;
  if(analysisMegaSelected.get(id)===analysisMegaStamp(p))analysisMegaSelected.delete(id);
  else analysisMegaSelected.set(id,analysisMegaStamp(p));
  return true;
}
document.addEventListener('click',event=>{
  const button=event.target.closest?.('[data-analysis-mega]');
  if(!button||!analysisToggleMega(button.dataset.analysisMega))return;
  const focused=button.dataset.analysisMega;
  if(typeof boxAnalysisSignature!=='undefined')boxAnalysisSignature='';
  if(typeof analysisSignature!=='undefined')analysisSignature='';
  if(typeof builderSignature!=='undefined')builderSignature='';
  renderBoxes();renderAnalysis();
  // Replacing cards must not lose the control used by keyboard users.
  for(const node of document.querySelectorAll('[data-analysis-mega]')){
    if(node.dataset.analysisMega===focused&&node.getClientRects().length){node.focus({preventScroll:true});break}
  }
});
