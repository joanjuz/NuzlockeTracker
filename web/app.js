'use strict';
// Startup and snapshot dispatch. Loaded last: every view script is ready.
function render(next){localState=next;if(!companionView)renderScreen(next)}
function renderScreen(next){
state=next;
$('game-name').textContent=state.game.replace(' 1.0','');
const gen6=GEN6_GAMES.includes(state.game);
const region=gen6?(state.game.startsWith('Pokémon')?'Kalos':'Hoenn'):'Alola';
$('game-region').textContent=region+' · versión 1.0'+(gen6?' (experimental)':'');
$('places-heading').textContent='Rutas de '+region;
$('route-intro').textContent='Sin menús desplegables. Marca «Fósil» junto a «Muerte». '
  +'Los intercambios se identifican con lecturas completas de '+(gen6?'31':'32')
  +' cajas; «Intercambiado» queda bajo MISS en rutas vacías.';
$('analysis-source-note').textContent=gen6?
  'Análisis aproximado con referencias USUM: confirmar habilidades, movimientos y formas en Gen6 antes de usarlo para decisiones.':
  state.game_data?.active?'Definitive Game Data y referencias USUM · Los registros ausentes usan CSV o referencia; no se simulan parches de combate.':
  'Referencia USUM · Puede variar con el randomizer.';
if(!companionView&&state.game_data)renderGameDataStatus(state.game_data);
$('box').disabled=$('living-dex').checked;
$('global').disabled=$('living-dex').checked;
$('living-dex-sprites').disabled=!$('living-dex').checked;
$('open-companion').disabled=gen6;
const totalBoxes=gen6?31:32;
if($('box').options?.length>=32){
  $('box').options[31].hidden=gen6;$('box').options[31].disabled=gen6;
}
if(gen6&&Number($('box').value)>31)$('box').value='1';
$('game').disabled=Boolean(state.demo)||companionView;
if(routeGame!==state.game){routeGame=state.game;placeSignature='';}
routeCatalog=routeCatalogFor(state.game);
$('eyebrow').textContent=companionView?'AVENTURA DE TU COMPAÑERO':state.demo?'MODO DEMO':'';
$('eyebrow').hidden=!companionView&&!state.demo;
renderMini();
$('dead-count').textContent=Object.keys(state.progress?.deaths||{}).length;
renderActiveView();
$('demo-tools').hidden=!state.demo;
if(state.demo){$('demo-scenario').value=state.demo_scenario;$('box').value=state.selected_box;}
renderConnectionStatus(state);
renderPartyCards(state);
$('scan-status').textContent=gen6?gen6ScanStatus(state):gen7ScanStatus(state);
$('cancel').hidden=companionView||!state.scan.active;
refreshOpenDetail(state);
}
// Native desktop bridge: file dialogs exist only inside the pywebview window.
async function exportWithDialog(kind){
 const button=$(kind==='diagnostic'?'diagnostic':'save-session');
 if(!button||button.disabled)return;
 const label=button.textContent;
 button.disabled=true;
 try{
   if(!window.pywebview?.api?.save_export)
     throw Error('El selector de archivos requiere abrir Pokémon Tracker desde su ejecutable de Windows.');
   const result=await window.pywebview.api.save_export(kind);
   if(result?.error)throw Error(result.error);
   if(result?.saved)showExportFeedback('Archivo guardado: '+result.name);
 }catch(error){showExportFeedback('No se pudo guardar: '+error.message);}
 finally{button.disabled=false;}
}
$('save-session').onclick=()=>exportWithDialog('session');$('diagnostic').onclick=()=>exportWithDialog('diagnostic');
function subscribe(){
  socket=new WebSocket(`ws://${location.host}/ws`);
  socket.onmessage=e=>{
    try{render(JSON.parse(e.data))}catch(error){console.error(error)}
  };
  socket.onclose=()=>{
    $('badge').textContent='Servidor local desconectado';
    $('badge').classList.remove('live');
    $('notice').hidden=false;
    $('notice').textContent='Mantén abierta la ventana del servidor. Intentando reconectar…';
    setTimeout(start,2000);
  };
  socket.onerror=()=>socket.close();
}
// Restores the connection form from the session the server saved last time.
function applySavedConnection(saved){
  $('game').value=saved.game;
  $('mode').value=saved.mode;
  $('pid').value=saved.pid??'';
  $('port').value=saved.port??24689;
  $('port-label').hidden=saved.mode!=='gdb';
  $('saved-session-status').textContent='Sesión guardada · '+saved.game+' · conexión automática al iniciar'
    +(saved.pid?' · PID '+saved.pid:'');
}
async function start(){
  try{
    const session=await getJSON('/api/session');
    token=session.token;
    scheduleUpdateCheck();
    if(typeof session.version==='string'&&/^\d+\.\d+\.\d+$/.test(session.version))setText($('app-version'),'Progressive '+session.version);
    await loadRunProfiles();
    document.title='Pokémon Tracker';
    const saved=session.saved_connection;
    if(saved)applySavedConnection(saved);
    analysisData=await getJSON('/api/analysis');
    render(await getJSON('/api/state'));
    subscribe();
  }catch(e){
    $('status').textContent='Esperando al servidor local…';
    setTimeout(start,2000);
  }
}
start();
