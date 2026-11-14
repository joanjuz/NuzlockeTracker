'use strict';
// Tabs, navigation strip, companion view switch and display preferences.
const views={dead:['Muertos',''],party:['Equipo actual',''],boxes:['Tus cajas',''],places:['Rutas',''],progress:['Progreso',''],analysis:['Análisis del equipo',''],overlay:['Diseñar overlay para OBS',''],connection:['Conexión','']};
function switchTab(tab){
  if(companionView&&(tab==='connection'||tab==='progress'))return;
  if(tab==='overlay'){
    // The overlay editor iframe loads lazily on its first visit.
    const frame=$('overlay-editor-frame');
    if(!frame.src)frame.src=frame.dataset.src;
  }
  document.querySelectorAll('nav button').forEach(b=>{
    const active=b.dataset.tab===tab;
    b.classList.toggle('active',active);
    if(active)b.setAttribute('aria-current','page');
    else b.removeAttribute('aria-current');
  });
  for(const key of Object.keys(views))$(key+'-view').hidden=key!==tab;
  $('title').textContent=views[tab][0];
  $('subtitle').textContent=views[tab][1];
  $('subtitle').hidden=!views[tab][1];
  renderActiveView();
  if(tab==='connection')refreshProcesses();
}
function renderActiveView(){
  if(!state)return;
  if(!$('boxes-view').hidden)renderBoxes();
  if(!$('places-view').hidden)renderPlaces();
  if(!$('progress-view').hidden)renderProgress();
  if(!$('dead-view').hidden)renderDead();
  if(!$('analysis-view').hidden)renderAnalysis();
}

// The editor reports its natural content height; only this iframe may resize it.
function resizeOverlayEditor(event){
  const frame=$('overlay-editor-frame'),data=event.data;
  if(event.origin!==location.origin||event.source!==frame.contentWindow||!data||data.type!=='tracker-overlay-resize')return;
  if(typeof data.height!=='number'||!Number.isFinite(data.height)||data.height<1||data.height>20000)return;
  frame.style.height=Math.max(240,Math.ceil(data.height))+'px';
  frame.style.minHeight='0';frame.setAttribute('scrolling','no');
}
window.addEventListener('message',resizeOverlayEditor);

function updateNavigationOverflow(){
  const nav=$('section-nav');if(!nav)return;
  const overflow=nav.scrollWidth>nav.clientWidth+1;
  $('nav-scroll-back').hidden=$('nav-scroll-forward').hidden=!overflow;
  $('nav-scroll-back').disabled=nav.scrollLeft<=1;
  $('nav-scroll-forward').disabled=nav.scrollLeft+nav.clientWidth>=nav.scrollWidth-1;
}
for(const [id,step] of [['nav-scroll-back',-1],['nav-scroll-forward',1]]){
  const button=$(id);if(button)button.onclick=()=>{$('section-nav').scrollBy({left:step*180,behavior:'auto'});};
}
if($('section-nav')){
  $('section-nav').addEventListener('scroll',updateNavigationOverflow);
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(updateNavigationOverflow).observe($('section-nav'));
  window.addEventListener('resize',updateNavigationOverflow);updateNavigationOverflow();
}

document.querySelectorAll('nav button').forEach(button=>button.onclick=()=>switchTab(button.dataset.tab));$('quick-connect').onclick=()=>switchTab('connection');
function setCompanionView(enabled,remote){
  if(companionView&&enabled){renderScreen(remote);return;}
  companionView=Boolean(enabled);$('quick-connect').hidden=companionView;$('quick-connect').disabled=companionView;selected=null;for(const id of ['detail','move-detail'])if($(id).open)$(id).close();
  miniSignature='';boxSignature='';placeSignature='';deadSignature='';analysisSignature='';analysisTeamSignature='';detailSignature='';
  $('box').value='1';
  document.querySelector('nav button[data-tab="connection"]').disabled=companionView;
  // Level caps are local to this run: a partner's view has none. A local draft is kept, not discarded.
  const progressTab=document.querySelector('nav button[data-tab="progress"]');if(progressTab)progressTab.disabled=companionView;
  renderScreen(companionView?remote:localState);
  if(companionView&&['connection','progress'].includes(document.querySelector('nav button.active')?.dataset.tab))switchTab('party');
}
window.setCompanionView=setCompanionView;
$('theme').value=document.documentElement.dataset.theme||'dark';$('theme').onchange=()=>{document.documentElement.dataset.theme=$('theme').value;try{localStorage.setItem('progressive-theme',$('theme').value)}catch(e){}};
// Compact view preference; storage may be unavailable, so failures keep the default.
let compact=false;
try{compact=localStorage.getItem('progressive-density')==='compact'}catch(e){}
function density(){
  document.body.classList.toggle('compact',compact);
  $('density').textContent=compact?'Vista amplia':'Vista compacta';
}
density();
$('density').onclick=()=>{
  compact=!compact;
  try{localStorage.setItem('progressive-density',compact?'compact':'comfortable')}catch(e){}
  density();
};
document.addEventListener('pointerdown',event=>{document.querySelectorAll('details[open]').forEach(menu=>{if(!menu.closest('dialog')&&!menu.contains(event.target))menu.open=false})});
document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('details[open]').forEach(menu=>menu.open=false)});
