'use strict';
// Connection status, local commands, templates and emulator discovery.
// Header status, live badge and reconnection notice (setText avoids re-announcing).
function renderConnectionStatus(snapshot){
  setText($('status'),String(snapshot.connection.message??'')+(snapshot.persist_warning&&!companionView?' · ⚠ '+String(snapshot.persist_warning):''));
  if(!companionView)showCommandError(snapshot.last_command_error);
  const connected=snapshot.connection.status==='connected'&&!snapshot.stale;
  setText($('badge'),connectionBadgeText(snapshot,connected));
  $('badge').classList.toggle('live',connected);
  $('notice').hidden=companionView||!snapshot.stale;
  setText($('notice'),'Última lectura · Esperando reconexión.');
}
function connectionBadgeText(snapshot,connected){
  if(companionView)return '● Última sesión';
  if(connected)return snapshot.demo?'● Demostración':snapshot.battle_hp?'● PS de combate':'● En vivo';
  if(snapshot.connection.status==='connecting')return 'Localizando RAM';
  if(snapshot.connection.status==='retrying')return 'Reconectando';
  return 'Sin datos actuales';
}
// A queued command (for example «Marcar muerto» twice) can be rejected by the
// worker after the HTTP request already returned 202: show it for a while.
let shownCommandError=null,commandErrorTimer=null;
function showCommandError(failed){
 if(!failed||typeof failed.message!=='string'||failed.at===shownCommandError)return;
 shownCommandError=failed.at;
 if(Date.now()/1000-Number(failed.at)>15)return;
 showExportFeedback('No se pudo completar: '+failed.message);
 clearTimeout(commandErrorTimer);
 commandErrorTimer=setTimeout(()=>{const note=$('export-feedback');if(note)note.hidden=true;},8000);
}
function showExportFeedback(message){
 const note=$('export-feedback');
 if(note){note.textContent=message;note.hidden=false;}
}
async function command(cmd){
  try{
    if(companionView)throw Error('La sesión del compañero es de solo lectura.');
    if(!token)throw Error('El servidor local aún no está disponible.');
    const response=await fetch('/api/command',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Tracker-Token':token},
      body:JSON.stringify(cmd)
    });
    const result=await response.json();
    if(!response.ok)throw Error(result.error||'No se pudo realizar la acción.');
  }catch(e){
    $('status').textContent=e.message;
  }
}
$('connect').onclick=()=>command({
  action:'connect',
  game:$('game').value,
  mode:$('mode').value,
  pid:$('pid').value?Number($('pid').value):null,
  port:Number($('port').value)
});
$('disconnect').onclick=()=>command({action:'disconnect'});
$('mode').onchange=()=>{$('port-label').hidden=$('mode').value!=='gdb'};
const filesToImport=[['moves','template-moves'],['stats','template-stats'],['evolutions','template-evolutions']];
async function templateStatus(){
  try{
    const r=await fetch('/api/templates');
    const j=await r.json();
    if(r.ok){
      $('template-status').textContent=`Plantillas guardadas: ${j.counts.moves} movimientos · ${j.counts.stats} especies · `
        +`${j.counts.evolutions} especies con evoluciones modificadas.`;
    }
  }catch(e){
    $('template-status').textContent=e.message;
  }
}
// Reads the chosen CSV files keyed by template kind; rejects oversized files.
async function readTemplateFiles(){
  const files={};
  for(const [key,id] of filesToImport){
    const file=$(id).files?.[0];
    if(!file)continue;
    if(file.size>180000)throw Error('Plantilla demasiado grande: '+file.name);
    files[key]=await file.text();
  }
  return files;
}
$('import-templates').onclick=async()=>{
  const button=$('import-templates');
  button.disabled=true;
  try{
    const files=await readTemplateFiles();
    if(!Object.keys(files).length)throw Error('Selecciona al menos un archivo CSV.');
    const r=await fetch('/api/templates',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Tracker-Token':token},
      body:JSON.stringify({files})
    });
    const j=await r.json();
    if(!r.ok)throw Error(j.error||'No se pudo importar');
    $('template-status').textContent='Plantillas importadas y guardadas. Los datos de equipo y cajas se actualizarán.';
    for(const [,id] of filesToImport)$(id).value='';
    await templateStatus();
  }catch(e){
    $('template-status').textContent='Error: '+e.message;
  }finally{
    button.disabled=false;
  }
};
templateStatus();

// DGD is a two-step local import: selecting/previewing never writes a profile.
let gameDataPreview=null,gameDataRequest=0;
function cancelGameDataPreview(){
  gameDataRequest++;gameDataPreview=null;
  if($('game-data-preview'))$('game-data-preview').hidden=true;
  if($('game-data-ack'))$('game-data-ack').checked=false;
  if($('game-data-profile'))$('game-data-profile').hidden=true;
}
function profileProvenanceText(profile){
  if(!profile||profile.state!=='historical')return profile?.reason||'Procedencia no disponible.';
  const titles={personal:'Pokémon: estadísticas, tipos y habilidades',moves:'Movimientos',trainers:'Entrenadores',
    evolutions:'Evoluciones',rng:'Semilla','pokemon-stats':'Estadísticas Pokémon','egg-moves':'Movimientos huevo',
    starters:'Iniciales','wild-encounters':'Encuentros salvajes','static-encounters':'Encuentros estáticos',
    trades:'Intercambios',tms:'MT','move-tutors':'Tutores',marts:'Tiendas',items:'Objetos','field-items':'Objetos de campo',
    pickup:'Recogida','shiny-rate':'Probabilidad shiny','personal-fields':'Campos Pokémon editados',
    record:'Entradas editadas',move:'Movimientos editados',learnset:'Movimientos por nivel','personal-flags':'Compatibilidades MT/tutores',
    typechart:'Tabla de tipos',shiny:'Probabilidad shiny',playercaps:'Player Level Caps',crointegrity:'Integridad CRO/CRR',
    shops6:'Tiendas',shops7:'Tiendas',machines7:'MT',tutors7:'Tutores','nature-mints':'Mentas'};
  const sections=profile.sections.map(id=>titles[id.split('/')[1]]||id).join(', ');
  return `Perfil: ${profile.name}\nAutor declarado: ${profile.author||'No indicado'}\nJuego de origen: ${profile.gameId==='ultra-moon'?'Ultra Luna':'Ultra Sol'}\nSecciones de la receta aplicada: ${sections}\n`
    +'Procedencia histórica declarada. No acredita coincidencia exacta con el perfil original ni con la ROM actual.\n'
    +(profile.subsequentChanges==='recorded'?'Hay cambios posteriores registrados.':'No constan cambios posteriores en el historial; puede haber cambios externos.');
}
function renderProfileProvenance(profile,preview=false){
  const card=$('game-data-profile');if(!card)return;
  card.hidden=!profile;
  if(!profile)return;
  $('game-data-profile-title').textContent=preview?'Perfil de origen · vista previa':'Perfil de origen';
  $('game-data-profile-text').textContent=profileProvenanceText(profile);
  $('game-data-profile-details').hidden=profile.state!=='historical';
  $('game-data-profile-hash').textContent=profile.state==='historical'?profile.recipeSha256:'';
}

function renderGameDataStatus(status){
  renderProfileProvenance(gameDataPreview?.selectedGame===$('game').value?gameDataPreview.profileProvenance:status.profileProvenance,!!gameDataPreview);
  const note=$('game-data-status');if(!note)return;
  $('remove-game-data').hidden=!status.loaded;
  note.textContent=status.error||(!status.loaded?'Sin datos DGD importados. Se usan las referencias y los CSV existentes.':
    `${status.game} · ${status.counts.species} especies/formas · ${status.counts.moves} movimientos · `
    +(status.active?'DGD activo para esta partida.':'Se activará solo al seleccionar y conectar el juego compatible.')
    +` Revisión: ${status.revision||'desconocida'}. ${status.warning||''}`
    +(status.active&&status.levelCaps?.state==='proposal'?' Incluye una propuesta de límites de nivel del Randomizer: revísala en Progreso; no se aplica sola.':''));
}
async function gameDataStatus(){
  if(!$('game-data-status'))return;
  try{const response=await fetch('/api/game-data'),result=await response.json();if(!response.ok)throw Error(result.error);renderGameDataStatus(result);}
  catch(error){$('game-data-status').textContent=error.message;}
}
async function gameDataPost(action,data){
  if(companionView)throw Error('La sesión del compañero es de solo lectura.');
  const response=await fetch('/api/game-data/'+action,{method:'POST',
    headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'No se pudo completar la importación DGD.');return result;
}
async function previewGameData(){
  cancelGameDataPreview();
  const request=gameDataRequest,button=$('preview-game-data'),game=$('game').value;
  button.disabled=true;
  try{
    const file=$('game-data-file').files?.[0];if(!file)throw Error('Selecciona el JSON exportado por Definitive Randomizer.');
    if(file.size>5000000)throw Error('El archivo DGD supera 5 MB.');
    const content=await file.text();
    if(request!==gameDataRequest)return;
    const result=await gameDataPost('preview',{content,game});
    if(request!==gameDataRequest||game!==$('game').value)return;
    gameDataPreview={...result,selectedGame:game};
    renderProfileProvenance(result.profileProvenance,true);
    $('game-data-summary').textContent=`${result.game} · ${result.counts.species} especies/formas · ${result.counts.moves} movimientos · ${result.counts.evolutions} listas de evoluciones. `
      +(result.replacesExisting?'Reemplazará la importación anterior de esta partida.':'Se guardará en esta partida.');
    $('game-data-differences').textContent=result.differences.length?result.differences.map(d=>`${d.record} · ${d.field}\nActual: ${JSON.stringify(d.before)}\nImportado: ${JSON.stringify(d.after)}`).join('\n\n'):'No se detectaron diferencias en la muestra comparada.';
    $('game-data-warning').textContent=result.warning;
    $('game-data-ack-label').hidden=!result.requiresRevisionAcknowledgement;
    $('apply-game-data').disabled=false;
    $('game-data-preview').hidden=false;
  }catch(error){if(request===gameDataRequest)$('game-data-status').textContent='Error: '+error.message;}
  finally{button.disabled=false;}
}
async function applyGameData(){
  const pending=gameDataPreview,button=$('apply-game-data');if(!pending)return;
  if(pending.selectedGame!==$('game').value){cancelGameDataPreview();return;}
  if(pending.requiresRevisionAcknowledgement&&!$('game-data-ack').checked){$('game-data-status').textContent='Confirma el aviso de revisión desconocida antes de importar.';return;}
  button.disabled=true;
  try{
    const result=await gameDataPost('apply',{previewToken:pending.previewToken,game:pending.selectedGame,acknowledgeUnknownRevision:$('game-data-ack').checked});
    cancelGameDataPreview();$('game-data-file').value='';renderGameDataStatus(result);
  }catch(error){$('game-data-status').textContent='Error: '+error.message;}
  finally{button.disabled=false;}
}
if($('preview-game-data')){
  $('preview-game-data').onclick=previewGameData;
  $('apply-game-data').onclick=applyGameData;
  $('cancel-game-data').onclick=()=>{cancelGameDataPreview();gameDataStatus();};
  $('game-data-file').onchange=cancelGameDataPreview;
  $('remove-game-data').onclick=async()=>{
    if(!confirm('¿Retirar los datos DGD de esta partida y volver a las referencias y los CSV existentes?'))return;
    try{renderGameDataStatus(await gameDataPost('remove',{}));cancelGameDataPreview();}
    catch(error){$('game-data-status').textContent='Error: '+error.message;}
  };
  $('game-data-settings').ontoggle=()=>{if($('game-data-settings').open)gameDataStatus();};
}

// Process discovery only suggests candidates; it never silently changes a PID.
let processCandidates=[],processRequest=0;
function showProcessCandidates(){
  const picker=$('process-picker');if(!picker)return;
  const selectedGame=$('game').value;
  picker.replaceChildren(new Option('Elegir un emulador abierto…',''));
  const ranked=[...processCandidates].sort((a,b)=>Number(b.game===selectedGame)-Number(a.game===selectedGame));
  for(const item of ranked){
    const mismatch=Boolean(item.game&&item.game!==selectedGame);
    const label=[item.pid,item.name,item.title||item.game||'Juego sin identificar'].filter(Boolean).join(' · ');
    const option=new Option(label,String(item.pid));option.disabled=mismatch;option.title=label+(mismatch?' · Selecciona su juego para usarlo.':'');picker.add(option);
  }
  picker.value='';
}
async function refreshProcesses(){
  const picker=$('process-picker'),button=$('refresh-processes');if(!picker||!button)return;
  const request=++processRequest;button.disabled=true;
  $('process-status').textContent='Buscando emuladores abiertos…';
  try{
    const response=await fetch('/api/processes',{cache:'no-store'}),result=await response.json();
    if(request!==processRequest)return;
    if(!response.ok||result.error)throw Error(result.error||'No se pudieron consultar los emuladores.');
    processCandidates=(result.processes||[]).filter(item=>Number.isInteger(item.pid)&&item.pid>0);
    showProcessCandidates();
    $('process-status').textContent=processCandidates.length?'Elige la ventana de tu partida; también puedes escribir el PID.':'No hay emuladores detectados. Puedes escribir el PID manualmente.';
  }catch(error){if(request===processRequest){processCandidates=[];showProcessCandidates();$('process-status').textContent=error.message+' Puedes escribir el PID manualmente.';}}
  finally{if(request===processRequest)button.disabled=false;}
}
if($('refresh-processes'))$('refresh-processes').onclick=refreshProcesses;
if($('process-picker'))$('process-picker').onchange=()=>{
  const item=processCandidates.find(item=>String(item.pid)===$('process-picker').value);
  if(!item||(item.game&&item.game!==$('game').value))return;
  $('pid').value=String(item.pid);$('process-status').textContent='Seleccionado PID '+item.pid+' · '+(item.title||item.name)+'.';
};
$('game').onchange=()=>{showProcessCandidates();cancelGameDataPreview();};
$('demo-scenario').onchange=()=>command({action:'demo',scenario:$('demo-scenario').value});
