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
$('game').onchange=showProcessCandidates;
$('demo-scenario').onchange=()=>command({action:'demo',scenario:$('demo-scenario').value});
