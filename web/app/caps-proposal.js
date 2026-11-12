'use strict';
// Level caps proposed by Definitive Randomizer (optional «playerLevelCaps» block of the imported
// game data). They are the mechanical limits its Player Level Caps patch enforces in that ROM,
// not the stages of the run: nothing is copied until the player reviews the proposal and accepts
// it explicitly. Accepting replaces the stage list through one atomic backend command that names
// the exact proposal and list that were reviewed; no stage is ever chosen as the current one.
const CAPS_FINAL_STAGE_NAME='Después del último punto (techo del parche)';
// null when no review is open: {identity, saved (signature), revision, replacing, busy, stale}.
let capsProposalReview=null,capsProposalSignature='',capsProposalNotice={text:'',error:false};

// --- Pure helpers (no DOM): exercised directly by tests/test_caps_proposal_ui.js.
function capsProposalOf(snapshot){const block=snapshot?.game_data?.active?snapshot.game_data.levelCaps:null;return block&&block.state!=='absent'?block:null}
function capsSourceOf(snapshot){return snapshot?.level_caps_source||{accepted:null,dismissed:null,matchesCurrent:false,error:null}}
function capsProposalIdentity(snapshot){
  const block=capsProposalOf(snapshot);
  return JSON.stringify([snapshot?.game??null,snapshot?.game_data?.fingerprint??null,block?.fingerprint??null,block?.tableSha256??null,block?.state??null]);
}
function sameProposal(record,block){return Boolean(record&&block&&record.tableSha256===block.tableSha256&&record.capsFingerprint===block.fingerprint)}
function proposalStages(block,finalStage){
  const stages=list(block?.stages).map(s=>({name:s.name,cap:s.cap}));
  if(finalStage)stages.push({name:CAPS_FINAL_STAGE_NAME,cap:block.ceiling});
  return stages;
}
function finalStageAllowed(block){return list(block?.stages).length<LEVEL_CAP_RULES.stages}
// Row by row: what the proposal would save next to what the run has now.
function proposalComparison(block,saved,finalStage){
  const proposed=proposalStages(block,finalStage),points=list(block?.checkpoints),rows=[];
  for(let i=0;i<Math.max(proposed.length,saved.length);i++){
    const next=proposed[i]||null,now=saved[i]||null;
    rows.push({n:i+1,next,now,condition:next&&points[i]?points[i].conditionText:next?'Techo del parche: rige cuando se completan todos los puntos':'',
      labelled:Boolean(next&&points[i]&&points[i].label),derived:Boolean(next&&!points[i]),
      same:Boolean(next&&now&&next.name===now.name&&next.cap===now.cap)});
  }
  return rows;
}
function shortDate(value){return typeof value==='string'&&value.length>=10?value.slice(0,10):'fecha desconocida'}
function shortHash(value){return typeof value==='string'&&value.length>16?value.slice(0,8)+'…'+value.slice(-8):String(value??'—')}
// What the Progreso card shows: {kind, title, text, detail, review, dismiss, restore}.
function capsProposalModel(snapshot,partner){
  const hidden={kind:'hidden'};
  if(partner||!snapshot)return hidden;
  const block=capsProposalOf(snapshot),source=capsSourceOf(snapshot),view=snapshot.level_caps,accepted=source.accepted;
  const origin=accepted&&view?.total?'Las etapas de esta partida se copiaron de una propuesta de Definitive Randomizer el '+shortDate(accepted.acceptedAt)
    +' ('+accepted.checkpoints+(accepted.checkpoints===1?' punto':' puntos')+(accepted.finalStage?' y la etapa final de Nv. 100':'')+'). '
    +(source.matchesCurrent?'No se han editado desde entonces.':'Después se editaron a mano: la lista actual ya no es la propuesta.'):'';
  if(view?.status==='unsupported')return hidden;
  if(!block)return origin?{kind:'origin',title:'Origen de las etapas',text:origin+' Los datos de Definitive Randomizer ya no están cargados; las etapas se conservan.'}
    :source.error?{kind:'notice',title:'Origen de las etapas',text:source.error}:hidden;
  if(block.state!=='proposal')
    return {kind:'notice',title:'Límites de Definitive Randomizer',text:block.reason||'',detail:block.detail||'',origin};
  const count=block.count,caps=list(block.stages).map(s=>s.cap);
  const summary=count+(count===1?' punto':' puntos')+' de Player Level Caps, de Nv. '+Math.min(...caps)+' a Nv. '+Math.max(...caps)+'.';
  if(sameProposal(accepted,block)&&source.matchesCurrent)
    return {kind:'accepted',title:'Propuesta de Definitive Randomizer en uso',text:origin,review:true,reviewLabel:'Ver la propuesta…'};
  if(sameProposal(source.dismissed,block))
    return {kind:'dismissed',title:'Propuesta de Definitive Randomizer descartada',
      text:'Descartaste esta propuesta el '+shortDate(source.dismissed.dismissedAt)+' y conservaste tus etapas. '+summary,
      origin,review:true,reviewLabel:'Revisar propuesta…',restore:true};
  return {kind:'proposal',title:'Propuesta de Definitive Randomizer',
    text:'Los datos importados incluyen '+summary+' Son los límites que el parche aplica en la ROM, no etapas de tu desafío: '
      +'revísalos y decide si quieres copiarlos como etapas de esta partida. No se ha cambiado nada.',
    origin,review:true,reviewLabel:'Revisar propuesta…',dismiss:true};
}

// --- Progreso card.
function renderCapsProposal(){
  const box=$('caps-proposal');if(!box)return;
  const partner=typeof companionView!=='undefined'&&companionView;
  const model=capsProposalModel(state,partner),dirty=typeof levelCapsDirty==='function'&&levelCapsDirty();
  const signature=JSON.stringify([model,dirty,capsProposalNotice,Boolean(capsProposalReview)]);
  if(capsProposalReview)watchCapsProposalReview();
  if(signature===capsProposalSignature)return;
  capsProposalSignature=signature;
  box.hidden=model.kind==='hidden';
  if(box.hidden){box.innerHTML='';return;}
  const blocked=dirty?'Tienes cambios sin guardar en las etapas: guárdalos o descártalos antes de revisar la propuesta.':'';
  const off=dirty||capsProposalReview?' disabled':'';
  box.dataset.kind=model.kind;
  box.innerHTML=`<div class="view-heading"><h2 id="caps-proposal-title">${esc(model.title)}</h2></div>`
    +`<p class="caps-note">${esc(model.text)}</p>`
    +(model.detail?`<p class="caps-note caps-proposal-detail">Detalle del Randomizer: ${esc(model.detail)}</p>`:'')
    +(model.origin&&model.kind!=='accepted'?`<p class="caps-note">${esc(model.origin)}</p>`:'')
    +(model.review||model.dismiss||model.restore?`<div class="caps-actions">`
      +(model.review?`<button type="button" class="${model.kind==='proposal'?'primary':''}" data-act="review" aria-describedby="caps-proposal-hint"${off}>${esc(model.reviewLabel)}</button>`:'')
      +(model.dismiss?`<button type="button" data-act="dismiss"${off}>Descartar propuesta</button>`:'')
      +(model.restore?`<button type="button" data-act="restore"${off}>Volver a mostrarla</button>`:'')+`</div>`:'')
    +`<p id="caps-proposal-hint" class="caps-note">${esc(blocked)}</p>`
    +`<p id="caps-proposal-status" class="caps-status${capsProposalNotice.error?' caps-lists-error':''}" role="${capsProposalNotice.error?'alert':'status'}" aria-live="polite">${esc(capsProposalNotice.text)}</p>`;
}
function capsProposalStatus(text,error){capsProposalNotice={text,error:Boolean(error)};renderCapsProposal();}
function proposalCommand(action,extra){
  const block=capsProposalOf(state);
  return {action,game:state.game,dataFingerprint:state.game_data.fingerprint,capsFingerprint:block.fingerprint,tableSha256:block.tableSha256,...extra};
}
async function dismissCapsProposal(dismissed){
  const block=capsProposalOf(state);
  if(!block||block.state!=='proposal'||capsProposalReview)return;
  try{
    await sendLevelCaps(proposalCommand('level_caps_dismiss_proposal',{dismissed}));
    capsProposalStatus(dismissed?'Propuesta descartada: tus etapas no cambiaron.':'La propuesta vuelve a estar disponible. No se cambió nada.',false);
  }catch(error){capsProposalStatus('No se pudo guardar la decisión: '+error.message,true);}
}

// --- Review dialog: preview, technical data, comparison and explicit confirmation.
function capsProposalBody(){
  const block=capsProposalOf(state),saved=savedStages(state),view=levelCapsOf(state),data=state.game_data;
  const finalOn=Boolean($('level-caps-proposal-final')?.checked)&&finalStageAllowed(block);
  const rows=proposalComparison(block,saved,finalOn).map(row=>`<tr${row.same?' class="same"':''}><th scope="row">${num(row.n)}</th>`
    +`<td>${row.next?`<span class="caps-proposal-line"><span class="caps-proposal-name">${esc(row.next.name)}</span><strong>Nv. ${num(row.next.cap)}</strong></span>`
      +`<small>${row.derived?'':row.labelled?'Nombre del catálogo del Randomizer · ':'Sin nombre en el catálogo · '}${esc(row.condition)}</small>`:'<span class="caps-proposal-none">—</span>'}</td>`
    +`<td>${row.now?`<span class="caps-proposal-line"><span class="caps-proposal-name">${esc(row.now.name)}</span><strong>Nv. ${num(row.now.cap)}</strong></span>`:'<span class="caps-proposal-none">—</span>'}</td></tr>`).join('');
  const hooks=block.hooks||{};
  const technical=[['Productor',(data.producer?.id||'—')+' '+(data.producer?.version||'')],['Juego',data.game||'—'],
    ['Estado del parche','instalado en Battle.cro ('+(hooks.battleCro||'—')+') y code.bin ('+(hooks.codeBin||'—')+')'],
    ['Cómo se aplica','los puntos se recorren en orden y rige el límite del primero sin completar; con todos completos, Nv. '+block.ceiling],
    ['Qué bloquea','la experiencia ganada en combate y el Caramelo Raro; no impide capturar ni recibir Pokémon de más nivel'],
    ['Huella de los datos importados',shortHash(data.fingerprint)],['Huella de Battle.cro y code.bin',shortHash(block.fingerprint)],
    ['Hash de la tabla del parche',shortHash(block.tableSha256)]]
    .map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('');
  const replace=saved.length?`<div class="caps-import-replace"><p><strong>Esta partida ya tiene ${num(saved.length)} ${saved.length===1?'etapa':'etapas'}</strong>`
      +`${view?.current_name?' (la vigente es «'+esc(view.current_name)+'»)':''}. Si aceptas, se reemplazan por completo; no se mezclan.</p>`
      +`<label class="checkbox"><input type="checkbox" id="level-caps-proposal-confirm"> Entiendo que se reemplazarán las etapas actuales</label></div>`:'';
  const finalNote=finalStageAllowed(block)?'':' No está disponible: la lista ya tiene el máximo de '+LEVEL_CAP_RULES.stages+' etapas.';
  return `<p class="caps-note">Estos son los límites que el parche <strong>Player Level Caps</strong> aplica en la ROM del proyecto exportado. `
    +`Son <strong>restricciones mecánicas del juego</strong>, no las etapas de tu desafío: si aceptas, se copian como etapas de esta partida y después puedes editarlas. Aún no se ha cambiado nada.</p>`
    +`<div class="caps-proposal-scroll"><table class="caps-proposal-table"><caption>Comparación con las etapas actuales de la partida</caption>`
    +`<thead><tr><th scope="col">#</th><th scope="col">Propuesta del Randomizer</th><th scope="col">Etapas actuales</th></tr></thead><tbody>${rows}</tbody></table></div>`
    +`<ul class="caps-import-notes"><li>Cada límite rige <strong>hasta</strong> completar su punto.</li>`
    +`<li>Ninguna etapa quedará vigente: la etapa vigente la eliges tú en Progreso. La opción de mostrar los límites no cambia.</li>`
    +`<li>El tracker no sabe qué puntos has completado: no lee esas condiciones de la partida.</li></ul>`
    +`<label class="checkbox caps-proposal-final"><input type="checkbox" id="level-caps-proposal-final"${finalOn?' checked':''}${finalStageAllowed(block)?'':' disabled'}> `
    +`Añadir una etapa final de Nv. ${num(block.ceiling)} («${esc(CAPS_FINAL_STAGE_NAME)}»). Es opcional: no es un punto del parche, sino su techo.${esc(finalNote)}</label>`
    +`<details class="caps-proposal-technical"><summary>Datos técnicos</summary><dl>${technical}</dl>`
    +`<p class="caps-note">Las huellas identifican los archivos exportados; no comprueban la ROM que ejecuta el emulador.</p></details>`
    +replace+`<p id="level-caps-proposal-error" class="caps-status caps-import-error" role="alert"></p>`;
}
function openCapsProposal(){
  const block=capsProposalOf(state),dialog=$('level-caps-proposal-dialog'),body=$('level-caps-proposal-body');
  if(!block||block.state!=='proposal'||capsProposalReview)return;
  if(typeof levelCapsDirty==='function'&&levelCapsDirty()){capsProposalStatus('Guarda o descarta los cambios de las etapas antes de revisar la propuesta.',true);return;}
  if(!dialog||!body||typeof dialog.showModal!=='function'){capsProposalStatus('Este navegador no permite abrir la vista previa.',true);return;}
  const saved=savedStages(state);
  capsProposalReview={identity:capsProposalIdentity(state),saved:stagesSignature(saved),revision:state.level_caps?.revision??null,
    replacing:saved.length>0,busy:false,stale:''};
  capsProposalNotice={text:'',error:false};
  // Start clean: the optional final stage is never carried over from an earlier review.
  body.innerHTML='';
  body.innerHTML=capsProposalBody();
  updateCapsProposalApply();
  renderCapsProposal();
  dialog.showModal();
}
// Why the open review can no longer be accepted, or '' while it still describes this run.
function capsProposalStaleReason(){
  if(!capsProposalReview)return '';
  if(capsProposalIdentity(state)!==capsProposalReview.identity)
    return 'La partida, el juego o los datos importados cambiaron mientras revisabas la propuesta. Ciérrala y vuelve a revisarla.';
  if(stagesSignature(savedStages(state))!==capsProposalReview.saved||(state.level_caps?.revision??null)!==capsProposalReview.revision)
    return 'Las etapas de la partida cambiaron mientras revisabas la propuesta. Ciérrala y vuelve a revisarla.';
  if(typeof levelCapsDirty==='function'&&levelCapsDirty())
    return 'Hay cambios sin guardar en las etapas: guárdalos o descártalos y vuelve a revisar la propuesta.';
  return '';
}
function watchCapsProposalReview(){
  if(!capsProposalReview||capsProposalReview.busy)return;
  const reason=capsProposalStaleReason();
  if(reason===capsProposalReview.stale)return;
  capsProposalReview.stale=reason;
  const node=$('level-caps-proposal-error');if(node)setText(node,reason);
  updateCapsProposalApply();
}
function updateCapsProposalApply(){
  const apply=$('level-caps-proposal-apply');if(!apply||!capsProposalReview)return;
  const confirm=$('level-caps-proposal-confirm');
  apply.disabled=capsProposalReview.busy||Boolean(capsProposalReview.stale)||(capsProposalReview.replacing&&!(confirm&&confirm.checked));
  setText(apply,capsProposalReview.replacing?'Aceptar y reemplazar las etapas':'Aceptar la propuesta');
  const dismiss=$('level-caps-proposal-dismiss');if(dismiss)dismiss.disabled=capsProposalReview.busy;
}
function closeCapsProposal(message){
  const dialog=$('level-caps-proposal-dialog');if(dialog?.open)dialog.close();
  const body=$('level-caps-proposal-body');if(body)body.innerHTML='';
  capsProposalReview=null;capsProposalSignature='';
  capsProposalStatus(message||'',false);
}
function keepCurrentCaps(){if(capsProposalReview?.busy)return;closeCapsProposal('Se conservan los límites actuales: no se cambió nada.');}
async function dismissFromReview(){
  if(!capsProposalReview||capsProposalReview.busy)return;
  closeCapsProposal('');
  await dismissCapsProposal(true);
}
async function acceptCapsProposal(){
  if(!capsProposalReview||capsProposalReview.busy)return;
  const showError=text=>{const node=$('level-caps-proposal-error');if(node)setText(node,text)};
  const confirm=$('level-caps-proposal-confirm');
  const stale=capsProposalStaleReason();
  if(stale){capsProposalReview.stale=stale;showError(stale);updateCapsProposalApply();return;}
  if(capsProposalReview.replacing&&!(confirm&&confirm.checked)){showError('Confirma que quieres reemplazar las etapas actuales.');return;}
  const block=capsProposalOf(state),finalStage=Boolean($('level-caps-proposal-final')?.checked)&&finalStageAllowed(block);
  capsProposalReview.busy=true;updateCapsProposalApply();showError('');
  const count=proposalStages(block,finalStage).length;
  try{
    // The backend builds the stages from the imported data itself; this only names what was reviewed.
    await sendLevelCaps(proposalCommand('level_caps_accept_proposal',{finalStage,replace:capsProposalReview.replacing,listRevision:capsProposalReview.revision}));
  }catch(error){
    // Atomic: the previous list is intact. Keep the review open to retry or keep the current caps.
    capsProposalReview.busy=false;updateCapsProposalApply();showError('No se aceptó y las etapas anteriores se conservan: '+error.message);return;
  }
  closeCapsProposal('Propuesta aceptada: '+count+(count===1?' etapa':' etapas')+'. Ninguna quedó vigente: elige la etapa vigente arriba.');
}
function capsProposalClick(event){
  const button=event.target?.closest?.('[data-act]');if(!button||button.disabled)return;
  if(button.dataset.act==='review')openCapsProposal();
  else if(button.dataset.act==='dismiss')dismissCapsProposal(true);
  else if(button.dataset.act==='restore')dismissCapsProposal(false);
}
function capsProposalChange(event){
  if(event.target?.id==='level-caps-proposal-confirm'){updateCapsProposalApply();return;}
  if(event.target?.id!=='level-caps-proposal-final'||!capsProposalReview||capsProposalReview.busy)return;
  // The comparison follows the option; the confirmation is asked again for the list now shown.
  const body=$('level-caps-proposal-body');if(body)body.innerHTML=capsProposalBody();
  const node=$('level-caps-proposal-error');if(node)setText(node,capsProposalReview.stale);
  updateCapsProposalApply();
}
if($('caps-proposal'))$('caps-proposal').addEventListener('click',capsProposalClick);
if($('level-caps-proposal-body'))$('level-caps-proposal-body').addEventListener('change',capsProposalChange);
if($('level-caps-proposal-keep'))$('level-caps-proposal-keep').addEventListener('click',keepCurrentCaps);
if($('level-caps-proposal-dismiss'))$('level-caps-proposal-dismiss').addEventListener('click',dismissFromReview);
if($('level-caps-proposal-apply'))$('level-caps-proposal-apply').addEventListener('click',acceptCapsProposal);
// Escape keeps the current caps: it never accepts anything.
if($('level-caps-proposal-dialog'))$('level-caps-proposal-dialog').addEventListener('cancel',event=>{event.preventDefault();keepCurrentCaps();});
