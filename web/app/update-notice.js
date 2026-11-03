'use strict';
// Update notice: asks the local server (GET /api/update) at startup and every 6 h.
// Any failure, including a server without the endpoint, stays silent.
const UPDATE_CHECK_INTERVAL=6*60*60*1000;
const UPDATE_DISMISSED_KEY='progressive-update-dismissed';
// Only release pages of this repository; no "..", "%" or characters outside a plain URL path.
const UPDATE_URL_PATTERN=/^https:\/\/github\.com\/joanjuz\/NuzlockeTracker\/(?!.*\.\.)[A-Za-z0-9\-._~\/?#=&+]*$/;
let updateCheckTimer=null;
function updateDownloadUrl(url){return typeof url==='string'&&UPDATE_URL_PATTERN.test(url)?url:null}
function dismissedUpdate(){try{return localStorage.getItem(UPDATE_DISMISSED_KEY)}catch(e){return null}}
function showUpdateNotice(info){
  const box=$('update-notice');if(!box)return;
  const latest=typeof info?.latest==='string'?info.latest.replace(/^v/,''):'';
  const url=updateDownloadUrl(info?.url);
  if(info?.update_available!==true||!/^\d+\.\d+\.\d+$/.test(latest)||!url||dismissedUpdate()===latest){box.hidden=true;return;}
  setText($('update-notice-version'),'v'+latest);
  $('update-notice-link').href=url;
  $('update-notice-link').setAttribute('aria-label','Descargar la versión '+latest+' desde GitHub');
  box.dataset.version=latest;
  box.hidden=false;
}
async function checkForUpdate(){
  try{showUpdateNotice(await getJSON('/api/update',{cache:'no-store'}))}catch(error){}
}
// Called by start() once the local server answers; later restarts reuse the same timer.
function scheduleUpdateCheck(){
  if(updateCheckTimer!==null)return;
  checkForUpdate();
  updateCheckTimer=setInterval(checkForUpdate,UPDATE_CHECK_INTERVAL);
}
if($('update-notice-dismiss'))$('update-notice-dismiss').onclick=()=>{
  const box=$('update-notice');box.hidden=true;
  try{localStorage.setItem(UPDATE_DISMISSED_KEY,box.dataset.version||'')}catch(e){}
};
