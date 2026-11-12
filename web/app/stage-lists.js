'use strict';
// Reusable stage lists: export the saved stages of a run to a small JSON file and import one into
// another run, with a preview and an explicit confirmation before replacing anything.
// The file holds names, caps and order only: no ids, current stage, display option or run data.
// Importing applies the whole list through the existing atomic «level_caps_set» command (new ids,
// no current stage); the backend validates it again. Nothing is changed while previewing.
const STAGE_LIST_FORMAT='progressive-tracker-stage-list';
const STAGE_LIST_VERSION=1;
const STAGE_LIST_MAX_BYTES=32*1024;
const STAGE_LIST_FILE='limites-de-nivel.json';
const STAGE_LIST_MAX_PROBLEMS=6;
// null when no preview is open: {stages, warnings, replacing, saved (signature), busy}.
let stageImport=null;

// --- Pure helpers (no DOM): exercised directly by tests/test_level_caps_ui.js.
function stageListDocument(stages){
  return {format:STAGE_LIST_FORMAT,version:STAGE_LIST_VERSION,stages:list(stages).map(s=>({name:s.name,cap:s.cap}))};
}
function stageListText(stages){return JSON.stringify(stageListDocument(stages),null,2)+'\n'}
function shortText(value,limit=40){const text=String(value);return text.length>limit?text.slice(0,limit)+'…':text}
// {ok:true, stages:[{name,cap}], warnings:[text]} or {ok:false, errors:[text]}. Strict on purpose:
// an unknown field is refused, so a shared file cannot carry anything this format does not define.
function parseStageList(text){
  const fail=(...errors)=>({ok:false,errors});
  if(typeof text!=='string')return fail('No se pudo leer el archivo.');
  if(text.length>STAGE_LIST_MAX_BYTES)return fail('El archivo es demasiado grande para ser una lista de etapas (máximo 32 KB).');
  let data;
  try{data=JSON.parse(text.replace(/^﻿/,''))}catch(error){return fail('El archivo no es un JSON válido.')}
  if(!data||typeof data!=='object'||Array.isArray(data)||data.format!==STAGE_LIST_FORMAT)
    return fail('El archivo no es una lista de etapas de Progressive Tracker.');
  if(typeof data.version!=='number'||!Number.isInteger(data.version)||data.version<1)return fail('La versión del archivo no es válida.');
  if(data.version>STAGE_LIST_VERSION)
    return fail('El archivo usa la versión '+data.version+' del formato y esta versión del tracker solo entiende la '+STAGE_LIST_VERSION+'. Actualiza el tracker para importarlo.');
  const extra=Object.keys(data).filter(key=>!['format','version','stages'].includes(key));
  if(extra.length)return fail('El archivo contiene campos que este formato no admite: '+extra.slice(0,3).map(key=>'«'+shortText(key)+'»').join(', ')+(extra.length>3?'…':'')+'.');
  if(!Array.isArray(data.stages))return fail('El archivo no contiene una lista de etapas.');
  if(!data.stages.length)return fail('La lista no tiene ninguna etapa.');
  if(data.stages.length>LEVEL_CAP_RULES.stages)return fail('La lista tiene '+data.stages.length+' etapas; el máximo es '+LEVEL_CAP_RULES.stages+'.');
  const errors=[],stages=[];
  data.stages.forEach((stage,i)=>{
    const where='Etapa '+(i+1)+': ';
    if(!stage||typeof stage!=='object'||Array.isArray(stage)){errors.push(where+'formato no válido.');return;}
    const unknown=Object.keys(stage).filter(key=>key!=='name'&&key!=='cap');
    if(unknown.length){errors.push(where+'campos no admitidos ('+unknown.slice(0,3).map(key=>'«'+shortText(key)+'»').join(', ')+').');return;}
    const name=typeof stage.name==='string'?stage.name.trim():'';
    if(typeof stage.name!=='string'||!name){errors.push(where+'falta el nombre.');return;}
    if(name.length>LEVEL_CAP_RULES.name){errors.push(where+'el nombre supera '+LEVEL_CAP_RULES.name+' caracteres.');return;}
    if(CAP_CONTROL_CHARACTERS.test(name)){errors.push(where+'el nombre contiene caracteres no válidos.');return;}
    if(typeof stage.cap!=='number'||!Number.isInteger(stage.cap)||stage.cap<LEVEL_CAP_RULES.min||stage.cap>LEVEL_CAP_RULES.max){
      errors.push(where+'el límite debe ser un número entero entre 1 y 100.');return;}
    stages.push({name,cap:stage.cap});
  });
  if(errors.length){
    const shown=errors.slice(0,STAGE_LIST_MAX_PROBLEMS);
    if(errors.length>shown.length)shown.push('… y '+(errors.length-shown.length)+' problemas más.');
    return fail(...shown);
  }
  const warnings=[];
  stages.forEach((stage,i)=>{if(i&&stage.cap<stages[i-1].cap)
    warnings.push('La etapa '+(i+1)+' «'+stage.name+'» (Nv. '+stage.cap+') tiene un nivel inferior al de la anterior (Nv. '+stages[i-1].cap+'). Es solo un aviso.');});
  return {ok:true,stages,warnings};
}
function stagesSignature(stages){return JSON.stringify(list(stages).map(s=>[s.id,s.name,s.cap]))}

// --- Toolbar state (buttons and hint), refreshed with every snapshot and every draft change.
function stageListState(){
  const raw=state?.level_caps,view=levelCapsOf(state);
  const saved=view?savedStages(state):[];
  const dirty=typeof levelCapsDirty==='function'&&levelCapsDirty();
  if(raw?.status==='unsupported')return {export:false,import:false,hint:'Los límites de esta partida los creó una versión más nueva del tracker: no se pueden exportar ni reemplazar desde aquí.'};
  return {export:saved.length>0,import:!dirty&&!stageImport,
    hint:dirty?'Tienes cambios sin guardar en las etapas. Guárdalos o descártalos antes de importar una lista; se exporta solo la lista guardada.'
      :saved.length?'':'Esta partida aún no tiene etapas: puedes importar una lista, pero no hay nada que exportar.'};
}
function renderStageListToolbar(){
  const exportButton=$('caps-export'),importButton=$('caps-import');if(!exportButton||!importButton)return;
  const model=stageListState();
  exportButton.disabled=!model.export;importButton.disabled=!model.import;
  const hint=$('caps-lists-hint');if(hint)setText(hint,model.hint);
}

// --- Export: native «Guardar como» in the desktop window, a normal download in a browser.
function setListStatus(text,isError){
  const ok=$('caps-lists-status'),bad=$('caps-lists-error');
  if(ok)setText(ok,isError?'':text);
  if(bad)setText(bad,isError?text:'');
}
async function exportStageList(){
  const saved=savedStages(state);
  if(!saved.length){setListStatus('No hay etapas guardadas que exportar.',true);return;}
  setListStatus('',false);
  try{
    if(window.pywebview?.api?.save_export){
      const result=await window.pywebview.api.save_export('level_caps');
      if(result?.error)throw Error(result.error);
      if(result?.saved)setListStatus('Lista exportada: '+result.name+'. Solo contiene nombres y niveles máximos.',false);
      else setListStatus('Exportación cancelada.',false);
      return;
    }
    const url=URL.createObjectURL(new Blob([stageListText(saved)],{type:'application/json'}));
    const link=document.createElement('a');
    link.href=url;link.download=STAGE_LIST_FILE;document.body.appendChild(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    setListStatus('Lista exportada ('+saved.length+(saved.length===1?' etapa':' etapas')+') como '+STAGE_LIST_FILE+'. Solo contiene nombres y niveles máximos.',false);
  }catch(error){setListStatus('No se pudo exportar: '+error.message,true);}
}

// --- Import: choose a file, preview it, confirm, apply.
function chooseStageList(){
  if(typeof levelCapsDirty==='function'&&levelCapsDirty()){
    setListStatus('Guarda o descarta los cambios de las etapas antes de importar una lista.',true);return;}
  if(stageImport)return;
  const input=$('caps-import-file');if(!input)return;
  setListStatus('',false);
  input.value='';
  input.click();
}
async function stageListFileChosen(){
  const input=$('caps-import-file'),file=input?.files?.[0];if(!file)return;
  if(typeof levelCapsDirty==='function'&&levelCapsDirty()){setListStatus('Guarda o descarta los cambios de las etapas antes de importar una lista.',true);return;}
  if(file.size>STAGE_LIST_MAX_BYTES){setListStatus('No se importó: el archivo es demasiado grande para ser una lista de etapas (máximo 32 KB).',true);return;}
  let text;
  try{text=await file.text()}catch(error){setListStatus('No se importó: no se pudo leer el archivo.',true);return;}
  const parsed=parseStageList(text);
  if(!parsed.ok){setListStatus('No se importó «'+shortText(file.name,60)+'»: '+parsed.errors.join(' '),true);return;}
  openStageImport(parsed,file.name);
}
function stageImportBody(preview,fileName){
  const saved=savedStages(state),view=levelCapsOf(state);
  const rows=preview.stages.map((s,i)=>`<li><span class="caps-import-n">${num(i+1)}</span><span class="caps-import-name">${esc(s.name)}</span><strong>Nv. ${num(s.cap)}</strong></li>`).join('');
  const notes=[...preview.warnings.map(w=>`<li>${esc(w)}</li>`)];
  notes.push(`<li>Ninguna etapa quedará vigente: elegirás la etapa vigente en Progreso. La opción de mostrar los límites no cambia.</li>`);
  const replace=saved.length?`<div class="caps-import-replace"><p><strong>Esta partida ya tiene ${num(saved.length)} ${saved.length===1?'etapa':'etapas'}</strong>`
      +`${view?.current_name?' (la vigente es «'+esc(view.current_name)+'»)':''}. Al importar se reemplazan por completo; no se mezclan.</p>`
      +`<label class="checkbox"><input type="checkbox" id="level-caps-import-confirm"> Entiendo que se reemplazará la lista actual</label></div>`:'';
  return `<p class="caps-note">Archivo: ${esc(shortText(fileName,60))} · ${num(preview.stages.length)} ${preview.stages.length===1?'etapa':'etapas'}. Revisa la lista: aún no se ha cambiado nada.</p>`
    +`<ol class="caps-import-list" aria-label="Etapas que se importarán, en orden">${rows}</ol>`
    +`<ul class="caps-import-notes">${notes.join('')}</ul>${replace}`
    +`<p id="level-caps-import-error" class="caps-status caps-import-error" role="alert"></p>`;
}
function openStageImport(preview,fileName){
  const dialog=$('level-caps-import-dialog'),body=$('level-caps-import-body');
  if(!dialog||!body||typeof dialog.showModal!=='function'){setListStatus('Este navegador no permite abrir la vista previa.',true);return;}
  stageImport={stages:preview.stages,warnings:preview.warnings,replacing:savedStages(state).length>0,
    saved:stagesSignature(savedStages(state)),busy:false};
  body.innerHTML=stageImportBody(preview,fileName);
  updateStageImportApply();
  renderStageListToolbar();
  dialog.showModal();
}
function updateStageImportApply(){
  const apply=$('level-caps-import-apply');if(!apply||!stageImport)return;
  const confirm=$('level-caps-import-confirm');
  apply.disabled=stageImport.busy||(stageImport.replacing&&!(confirm&&confirm.checked));
  setText(apply,stageImport.replacing?'Reemplazar la lista':'Importar lista');
}
function closeStageImport(){
  const dialog=$('level-caps-import-dialog');if(dialog?.open)dialog.close();
  stageImport=null;renderStageListToolbar();
  const importButton=$('caps-import');if(importButton&&!importButton.disabled&&typeof importButton.focus==='function')importButton.focus();
}
function cancelStageImport(){if(stageImport?.busy)return;closeStageImport();setListStatus('Importación cancelada: no se cambió nada.',false);}
async function applyStageImport(){
  if(!stageImport||stageImport.busy)return;
  const showError=text=>{const node=$('level-caps-import-error');if(node)setText(node,text)};
  const confirm=$('level-caps-import-confirm');
  if(stageImport.replacing&&!(confirm&&confirm.checked)){showError('Confirma que quieres reemplazar la lista actual.');return;}
  if(typeof levelCapsDirty==='function'&&levelCapsDirty()){showError('Hay cambios sin guardar en las etapas: guárdalos o descártalos y vuelve a importar.');return;}
  if(stagesSignature(savedStages(state))!==stageImport.saved){
    showError('Las etapas de la partida cambiaron mientras revisabas la vista previa. Cierra esta ventana y vuelve a importar el archivo.');return;}
  stageImport.busy=true;updateStageImportApply();showError('');
  const count=stageImport.stages.length;
  try{
    // No ids and no «current»: the backend creates new ids and no stage is chosen. «show» is untouched.
    await sendLevelCaps({action:'level_caps_set',stages:stageImport.stages.map(s=>({name:s.name,cap:s.cap}))});
  }catch(error){
    // The command is atomic: the previous list is intact. Keep the preview open to retry or cancel.
    stageImport.busy=false;updateStageImportApply();showError('No se importó y la lista anterior se conserva: '+error.message);return;
  }
  closeStageImport();
  setListStatus('Lista importada: '+count+(count===1?' etapa':' etapas')+'. Elige la etapa vigente en Progreso.',false);
}
if($('caps-export'))$('caps-export').addEventListener('click',exportStageList);
if($('caps-import'))$('caps-import').addEventListener('click',chooseStageList);
if($('caps-import-file'))$('caps-import-file').addEventListener('change',stageListFileChosen);
if($('level-caps-import-cancel'))$('level-caps-import-cancel').addEventListener('click',cancelStageImport);
if($('level-caps-import-apply'))$('level-caps-import-apply').addEventListener('click',applyStageImport);
if($('level-caps-import-body'))$('level-caps-import-body').addEventListener('change',event=>{if(event.target?.id==='level-caps-import-confirm')updateStageImportApply()});
// Escape closes the preview without applying anything.
if($('level-caps-import-dialog'))$('level-caps-import-dialog').addEventListener('cancel',event=>{event.preventDefault();cancelStageImport();});
