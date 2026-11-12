'use strict';
// Manual level caps: header chip, over-cap labels on the party cards and the Progreso view.
// The player defines every stage. Caps are informative only: nothing here reads RAM, blocks
// an action or changes deaths and encounters. The backend validates every command again.
const LEVEL_CAP_RULES=Object.freeze({stages:64,name:60,min:1,max:100});
const CAP_CONTROL_CHARACTERS=new RegExp('[\u0000-\u001f\u007f-\u009f\u2028\u2029]');
// capsDraft: edited copy of the stage list (null when nothing is being edited). Each row keeps
// its stable id; rows added here carry only a local key until the backend assigns an id.
let capsDraft=null,capsErrors={},capsSaving=null,capsNewKey=0,capsEditorSignature='',capsCurrentSignature='',capsLeaveResolve=null;

// --- Pure helpers (no DOM): exercised directly by tests/test_level_caps_ui.js.
function levelCapsOf(snapshot){const view=snapshot?.level_caps;return view&&view.status==='ok'?view:null}
function savedStages(snapshot){return list(levelCapsOf(snapshot)?.stages).map(s=>({id:s.id,name:s.name,cap:s.cap}))}
// The cap that applies now, or null: hidden caps and «Sin etapa vigente» never mark Pokémon.
function activeLevelCap(snapshot){
  const view=levelCapsOf(snapshot);
  if(!view||!view.show||!view.total||typeof view.current_cap!=='number')return null;
  return {cap:view.current_cap,name:view.current_name};
}
function levelsOverCap(p,cap){
  if(!p||!cap||p.egg===true||typeof p.level!=='number'||!Number.isInteger(p.level))return 0;
  return Math.max(0,p.level-cap.cap);
}
// Header chip: hidden without stages, with show=false or for a partner's snapshot.
function levelCapChip(snapshot,partner){
  const view=levelCapsOf(snapshot);
  if(partner||!view||!view.show||!view.total)return null;
  const cap=activeLevelCap(snapshot);
  if(!cap)return {kind:'neutral',text:'Sin etapa vigente',over:0,label:'Límite de nivel: sin etapa vigente. Abrir Progreso.'};
  const over=list(snapshot.party).filter(p=>levelsOverCap(p,cap)>0).length;
  const text='Límite Nv. '+cap.cap+' · '+cap.name+(over?' · '+over+' por encima':'');
  return {kind:over?'warn':'ok',text,over,label:'Límite de nivel '+cap.cap+', etapa '+cap.name
    +(over?'. '+over+(over===1?' Pokémon del equipo lo supera':' Pokémon del equipo lo superan'):'')+'. Abrir Progreso.'};
}
// Party card label; '' when the Pokémon is within the cap or caps do not apply.
function overCapLabel(p){
  if(typeof companionView!=='undefined'&&companionView)return '';
  const over=levelsOverCap(p,activeLevelCap(state));
  return over?`<span class="over-cap" title="Aviso informativo: el límite vigente es ${num(activeLevelCap(state).cap)}">+${num(over)} sobre el límite</span>`:'';
}
function levelCapSignature(){const cap=(typeof companionView!=='undefined'&&companionView)?null:activeLevelCap(state);return cap?String(cap.cap):'-'}
// Client-side copy of the backend rules, so each row shows its own message before sending.
function stageProblem(row){
  const name=typeof row.name==='string'?row.name.trim():'';
  if(!name)return 'Escribe un nombre.';
  if(name.length>LEVEL_CAP_RULES.name)return 'Máximo '+LEVEL_CAP_RULES.name+' caracteres.';
  if(CAP_CONTROL_CHARACTERS.test(name))return 'El nombre contiene caracteres no válidos.';
  const cap=typeof row.cap==='number'?row.cap:Number(String(row.cap??'').trim());
  if(String(row.cap??'').trim()===''||!Number.isInteger(cap)||cap<LEVEL_CAP_RULES.min||cap>LEVEL_CAP_RULES.max)
    return 'El límite debe ser un número entero entre 1 y 100.';
  return '';
}
function draftErrors(rows){
  const errors={};
  for(const row of rows){const problem=stageProblem(row);if(problem)errors[row.key]=problem;}
  return errors;
}
// Rows whose cap is lower than the previous row: informative, never blocks saving.
function decreasingKeys(rows){
  const keys=new Set();
  rows.forEach((row,i)=>{if(i&&Number(row.cap)<Number(rows[i-1].cap)&&!stageProblem(row)&&!stageProblem(rows[i-1]))keys.add(row.key)});
  return keys;
}
function stagesPayload(rows){return rows.map(row=>{const stage={name:row.name.trim(),cap:Number(String(row.cap).trim())};return row.id?{id:row.id,...stage}:stage})}
function draftDiffers(rows,saved){
  if(rows.length!==saved.length)return true;
  return rows.some((row,i)=>row.id!==saved[i].id||row.name.trim()!==saved[i].name||String(row.cap).trim()!==String(saved[i].cap));
}
function levelCapsDirty(){return Boolean(capsDraft)&&!capsSaving&&draftDiffers(capsDraft,savedStages(state))}

// --- Header chip and party cards (every snapshot).
function renderLevelCapIndicators(snapshot){
  if(!(typeof companionView!=='undefined'&&companionView))settleLevelCapsSave(snapshot);
  const chip=$('level-cap-chip');if(!chip)return;
  const model=levelCapChip(snapshot,typeof companionView!=='undefined'&&companionView);
  chip.hidden=!model;
  if(model){
    setText(chip,model.text);
    chip.setAttribute('aria-label',model.label);
    chip.dataset.kind=model.kind;
  }
  const marker=$('progress-unsaved');if(marker)marker.hidden=!levelCapsDirty();
}

// --- Progreso view.
function renderProgress(){
  if(!state)return;
  renderCapsCurrent();
  renderCapsEditor();
}
function renderCapsCurrent(){
  const box=$('caps-current');if(!box)return;
  const raw=state.level_caps,view=levelCapsOf(state);
  const party=list(state.party).map(p=>p?[p.nickname||p.species,p.level,p.egg===true]:null);
  const signature=JSON.stringify([raw?.status,view,party,capsDraft?1:0]);
  if(signature===capsCurrentSignature)return;
  capsCurrentSignature=signature;
  if(raw?.status==='unsupported'){
    box.innerHTML='<p class="caps-note">Los límites de esta partida los creó una versión más nueva del tracker. Se conservan, pero no se pueden mostrar ni modificar aquí.</p>';return;
  }
  if(!view||!view.total){
    box.innerHTML=(view?.removed_current?removedNotice(view.removed_current):'')
      +'<div class="caps-empty"><p>Esta partida no tiene etapas de límite de nivel.</p>'
      +(capsDraft?'<p class="caps-note">Completa la etapa en la lista de abajo y pulsa «Guardar cambios».</p>'
        :'<button type="button" class="primary" data-act="add-first">Añadir la primera etapa</button>')+'</div>';
    return;
  }
  const index=typeof view.current_index==='number'?view.current_index:-1;
  const current=index>=0?view.stages[index]:null;
  const percent=current?Math.round((index+1)/view.total*100):0;
  const options=['<option value="">Sin etapa vigente</option>',...view.stages.map((s,i)=>
    `<option value="${esc(s.id)}"${s.id===view.current?' selected':''}>${num(i+1)}. ${esc(s.name)} · Nv. ${num(s.cap)}</option>`)].join('');
  box.innerHTML=`<div class="caps-current-card">`
    +`<small class="caps-kicker">ETAPA VIGENTE</small>`
    +(current?`<strong class="caps-level">Nv. ${num(current.cap)}</strong><p class="caps-stage-name">${esc(current.name)}</p>`
      +`<p class="caps-position">Etapa ${num(index+1)} de ${num(view.total)}</p>`
      :`<strong class="caps-level caps-none">Sin etapa vigente</strong><p class="caps-position">Elige una etapa para aplicar su límite.</p>`)
    +`<div class="caps-track" role="progressbar" aria-label="Avance por las etapas" aria-valuemin="0" aria-valuemax="${num(view.total)}" aria-valuenow="${num(index+1)}" aria-valuetext="${current?'Etapa '+num(index+1)+' de '+num(view.total):'Sin etapa vigente'}"><span style="width:${percent}%"></span></div>`
    +`<div class="caps-nav"><button type="button" data-act="previous"${index>0?'':' disabled'}>Etapa anterior</button>`
    +`<button type="button" data-act="next"${index>=0&&index<view.total-1?'':' disabled'}>Siguiente etapa</button></div>`
    +(view.removed_current?removedNotice(view.removed_current):'')
    +`<label>Elegir la etapa vigente<select id="caps-select">${options}</select></label>`
    +`<label class="checkbox caps-show"><input type="checkbox" id="caps-show"${view.show?' checked':''}> Mostrar el límite en la cabecera y en las fichas</label>`
    +`</div>`+capsTeam(current);
}
function removedNotice(removed){
  return `<p class="caps-note caps-removed" role="note">Se eliminó la etapa vigente «${esc(removed.name)}» (Nv. ${num(removed.cap)}). No se eligió otra: selecciona la etapa vigente.</p>`;
}
function capsTeam(current){
  const members=list(state.party).filter(Boolean);
  if(!current)return '';
  if(!members.length)return '<p class="caps-note">Sin equipo leído: conecta el tracker para comparar niveles.</p>';
  const cap={cap:current.cap};
  return '<div class="caps-team"><h3>Equipo frente al límite</h3><ul>'+members.map(p=>{
    const over=levelsOverCap(p,cap),level=typeof p.level==='number'?p.level:null;
    return `<li class="${over?'over':''}"><span>${esc(p.nickname||p.species)}</span><span>${level===null?'Nivel desconocido':'Nv. '+num(level)}</span>`
      +`<strong>${level===null?'—':over?'+'+num(over)+' sobre el límite':'Dentro del límite'}</strong></li>`;
  }).join('')+'</ul><p class="caps-note">Aviso informativo: el tracker no impide subir de nivel ni cambia nada en la partida.</p></div>';
}
function editorRows(){return capsDraft||savedStages(state).map(s=>({key:s.id,id:s.id,name:s.name,cap:String(s.cap)}))}
function renderCapsEditor(force){
  const box=$('caps-editor');if(!box)return;
  const view=levelCapsOf(state),raw=state.level_caps;
  box.hidden=raw?.status==='unsupported'||(!view?.total&&!capsDraft);
  if(box.hidden){capsEditorSignature='';return;}
  const rows=editorRows(),errors=capsErrors,decreasing=decreasingKeys(rows);
  const signature=JSON.stringify([rows.map(r=>r.key),capsDraft?1:0,errors,capsSaving?1:0,view?.current,view?.stages]);
  if(!force&&signature===capsEditorSignature){updateRowNotes();return;}
  capsEditorSignature=signature;
  const editable=!capsSaving;
  box.innerHTML=`<div class="view-heading"><h2>Etapas</h2><span id="caps-editor-state">${capsDraft&&levelCapsDirty()?'Cambios sin guardar':''}</span></div>`
    +`<p class="caps-note">El orden de la lista es el orden de la aventura. Los cambios se aplican juntos al pulsar «Guardar cambios».</p>`
    +`<div class="caps-table" role="table" aria-label="Etapas de límite de nivel">`
    +`<div class="caps-row caps-head" role="row"><span role="columnheader">#</span><span role="columnheader">Nombre de la etapa</span><span role="columnheader">Nivel máximo</span><span role="columnheader">Acciones</span></div>`
    +rows.map((row,i)=>capsRow(row,i,rows.length,errors[row.key],decreasing.has(row.key),editable,view)).join('')
    +`</div><div class="caps-actions"><button type="button" data-act="add"${editable&&rows.length<LEVEL_CAP_RULES.stages?'':' disabled'}>Añadir etapa</button>`
    +`<span class="caps-limit">${num(rows.length)} de ${LEVEL_CAP_RULES.stages} etapas</span>`
    +`<button type="button" data-act="discard"${capsDraft&&editable?'':' disabled'}>Descartar</button>`
    +`<button type="button" class="primary" data-act="save"${capsDraft&&editable?'':' disabled'}>Guardar cambios</button></div>`
    +`<p id="caps-editor-status" class="caps-status" role="status" aria-live="polite"></p>`;
}
function capsRow(row,i,total,error,lower,editable,view){
  const n=i+1,errorId='caps-error-'+esc(row.key),off=editable?'':' disabled';
  const current=row.id&&view?.current===row.id;
  return `<div class="caps-row${error?' invalid':''}" role="row" data-key="${esc(row.key)}">`
    +`<span role="cell" class="caps-index">${num(n)}${current?' <small class="caps-current-mark">vigente</small>':''}</span>`
    +`<span role="cell"><input data-field="name" value="${esc(row.name)}" maxlength="${LEVEL_CAP_RULES.name+20}" aria-label="Nombre de la etapa ${n}"${error?` aria-invalid="true" aria-describedby="${errorId}"`:''}${off}></span>`
    +`<span role="cell"><input data-field="cap" inputmode="numeric" value="${esc(row.cap)}" aria-label="Nivel máximo de la etapa ${n}"${error?` aria-invalid="true" aria-describedby="${errorId}"`:''}${off}></span>`
    +`<span role="cell" class="caps-row-actions"><button type="button" data-act="up" aria-label="Subir la etapa ${n}"${i&&editable?'':' disabled'}>↑</button>`
    +`<button type="button" data-act="down" aria-label="Bajar la etapa ${n}"${i<total-1&&editable?'':' disabled'}>↓</button>`
    +`<button type="button" data-act="remove" aria-label="Eliminar la etapa ${n}"${off}>Eliminar</button></span>`
    +`<p class="caps-row-note" role="cell" data-note="${esc(row.key)}" id="${errorId}">${rowNote(error,lower)}</p></div>`;
}
function rowNote(error,lower){return error?esc(error):lower?'Nivel inferior al de la etapa anterior: es solo un aviso, se puede guardar.':''}
// Typing never rebuilds the table (focus and caret stay); only the notes change.
function updateRowNotes(){
  const box=$('caps-editor');if(!box||!capsDraft||typeof box.querySelector!=='function')return;
  const lower=decreasingKeys(capsDraft);
  for(const row of capsDraft){
    const note=box.querySelector(`[data-note="${row.key}"]`);
    if(note)note.textContent=capsErrors[row.key]?capsErrors[row.key]:lower.has(row.key)?'Nivel inferior al de la etapa anterior: es solo un aviso, se puede guardar.':'';
  }
  const label=$('caps-editor-state');if(label)setText(label,levelCapsDirty()?'Cambios sin guardar':'');
  // Editing an existing row does not rebuild the table: enable its actions here.
  for(const act of ['save','discard']){const button=box.querySelector(`[data-act="${act}"]`);if(button)button.disabled=!capsDraft||Boolean(capsSaving);}
  renderLevelCapIndicators(state);
}
function startDraft(){if(!capsDraft)capsDraft=editorRows().map(row=>({...row}));return capsDraft}
function newStage(){capsNewKey+=1;return {key:'nueva-'+capsNewKey,id:null,name:'',cap:''}}
function focusRow(key,field){
  const box=$('caps-editor');if(!box||typeof box.querySelector!=='function')return;
  // Keys are stage ids ([A-Za-z0-9_-]) or local «nueva-N» keys: safe inside a selector.
  const target=box.querySelector(`[data-key="${key}"] ${field}`);if(target)target.focus();
}
function editorStatus(text){const node=$('caps-editor-status');if(node)setText(node,text)}
async function sendLevelCaps(cmd){
  if(typeof companionView!=='undefined'&&companionView)throw Error('La sesión del compañero es de solo lectura.');
  if(!token)throw Error('El servidor local aún no está disponible.');
  const response=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify(cmd)});
  const result=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(result.error||'No se pudo guardar.');
}
async function saveLevelCaps(){
  if(!capsDraft||capsSaving)return;
  capsErrors=draftErrors(capsDraft);
  const invalid=Object.keys(capsErrors);
  if(invalid.length){
    renderCapsEditor(true);
    editorStatus(invalid.length===1?'Hay una etapa con errores; revisa el mensaje junto a la fila.':'Hay '+invalid.length+' etapas con errores; revisa los mensajes junto a cada fila.');
    focusRow(invalid[0],'input');return;
  }
  capsSaving={before:JSON.stringify(savedStages(state)),at:Date.now()};renderCapsEditor(true);editorStatus('Guardando…');
  try{
    await sendLevelCaps({action:'level_caps_set',stages:stagesPayload(capsDraft)});
    editorStatus('Etapas guardadas.');
    // The draft stays visible (read-only) until the new list arrives through the snapshot.
    setTimeout(()=>{if(capsSaving){capsSaving=null;capsDraft=null;capsErrors={};renderProgress();renderLevelCapIndicators(state);}},4000);
  }catch(error){
    capsSaving=null;renderCapsEditor(true);editorStatus('No se guardó: '+error.message);
  }
}
function discardLevelCaps(){capsDraft=null;capsErrors={};capsSaving=null;capsEditorSignature='';renderProgress();renderLevelCapIndicators(state);editorStatus('Cambios descartados.');}
// A snapshot with a different saved list ends a pending save.
function settleLevelCapsSave(snapshot){
  if(!capsSaving)return;
  if(JSON.stringify(savedStages(snapshot))!==capsSaving.before){capsSaving=null;capsDraft=null;capsErrors={};capsEditorSignature='';}
}
function capsStageAt(offset){
  const view=levelCapsOf(state);if(!view)return null;
  const index=(typeof view.current_index==='number'?view.current_index:-1)+offset;
  return index>=0&&index<view.total?view.stages[index]:null;
}
function capsClick(event){
  const button=event.target?.closest?.('[data-act]');if(!button||button.disabled)return;
  const act=button.dataset.act,row=button.closest?.('[data-key]'),key=row?.dataset.key;
  if(act==='add-first'||act==='add'){
    const rows=startDraft();if(rows.length>=LEVEL_CAP_RULES.stages)return;
    const stage=newStage();rows.push(stage);renderProgress();renderLevelCapIndicators(state);focusRow(stage.key,'[data-field="name"]');return;
  }
  if(act==='save'){saveLevelCaps();return;}
  if(act==='discard'){discardLevelCaps();return;}
  if(act==='previous'||act==='next'){
    const target=capsStageAt(act==='next'?1:-1);
    if(target)command({action:'level_caps_current',stage:target.id});
    return;
  }
  if(!key)return;
  const rows=startDraft(),i=rows.findIndex(r=>r.key===key);if(i<0)return;
  if(act==='remove'){
    const removed=rows.splice(i,1)[0];delete capsErrors[key];
    renderCapsEditor(true);renderLevelCapIndicators(state);
    const view=levelCapsOf(state);
    editorStatus(removed.id&&removed.id===view?.current
      ?'Eliminaste la etapa vigente: al guardar, la partida quedará sin etapa vigente hasta que elijas otra.'
      :'Etapa eliminada de la lista. Guarda para aplicarlo.');
    const next=rows[Math.min(i,rows.length-1)];if(next)focusRow(next.key,'[data-act="remove"]');
    return;
  }
  const j=act==='up'?i-1:act==='down'?i+1:-1;if(j<0||j>=rows.length)return;
  [rows[i],rows[j]]=[rows[j],rows[i]];renderCapsEditor(true);renderLevelCapIndicators(state);
  editorStatus('Etapa movida a la posición '+(j+1)+'.');focusRow(key,`[data-act="${act}"]`);
}
function capsInput(event){
  const field=event.target?.dataset?.field,key=event.target?.closest?.('[data-key]')?.dataset.key;
  if(!field||!key)return;
  const rows=startDraft(),row=rows.find(r=>r.key===key);if(!row)return;
  row[field]=event.target.value;
  if(capsErrors[key]&&!stageProblem(row))delete capsErrors[key];
  updateRowNotes();
}
function capsChange(event){
  if(event.target?.id==='caps-select'){command({action:'level_caps_current',stage:event.target.value||null});return;}
  if(event.target?.id==='caps-show')command({action:'level_caps_show',show:Boolean(event.target.checked)});
}
// Navigation inside the tracker keeps the draft; only leaving the page or the run asks first.
function confirmLevelCapsLeave(){
  if(!levelCapsDirty())return Promise.resolve(true);
  const dialog=$('level-caps-leave-dialog');
  if(!dialog||typeof dialog.showModal!=='function')return Promise.resolve(false);
  return new Promise(resolve=>{capsLeaveResolve=resolve;dialog.showModal();});
}
function finishLevelCapsLeave(discard){
  const dialog=$('level-caps-leave-dialog');if(dialog?.open)dialog.close();
  if(discard){capsDraft=null;capsErrors={};capsSaving=null;capsEditorSignature='';}
  const resolve=capsLeaveResolve;capsLeaveResolve=null;if(resolve)resolve(discard);
}
for(const [id,handler] of [['caps-current',capsClick],['caps-editor',capsClick]]){const node=$(id);if(node)node.addEventListener('click',handler);}
if($('caps-editor'))$('caps-editor').addEventListener('input',capsInput);
if($('caps-current'))$('caps-current').addEventListener('change',capsChange);
if($('level-cap-chip'))$('level-cap-chip').addEventListener('click',()=>switchTab('progress'));
if($('level-caps-leave-keep'))$('level-caps-leave-keep').addEventListener('click',()=>finishLevelCapsLeave(false));
if($('level-caps-leave-discard'))$('level-caps-leave-discard').addEventListener('click',()=>finishLevelCapsLeave(true));
if($('level-caps-leave-dialog'))$('level-caps-leave-dialog').addEventListener('cancel',()=>finishLevelCapsLeave(false));
window.addEventListener('beforeunload',event=>{if(levelCapsDirty()){event.preventDefault();event.returnValue='';}});
