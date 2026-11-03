'use strict';
// Loads /companion.js after the DOM is ready.
// Optional Companion dependency can be recovered after a transient local load failure.
let companionRetryPending=false;
function companionScriptFailed(){
  companionRetryPending=false;
  $('companion-load-error').hidden=false;
  $('companion-load-retry').disabled=false;
}
window.companionScriptFailed=companionScriptFailed;
// Loaded from here (not an inline onerror attribute) so the page can run
// under a Content-Security-Policy without inline scripts.
function loadCompanion(){
  const script=document.createElement('script');script.src='/companion.js';
  script.onload=()=>{companionRetryPending=false;$('companion-load-error').hidden=true;};
  script.onerror=companionScriptFailed;document.body.append(script);
}
$('companion-load-retry').onclick=()=>{
  if(companionRetryPending)return;
  companionRetryPending=true;$('companion-load-retry').disabled=true;
  loadCompanion();
};
// companion.js reads dialogs declared after app.js: wait for the full DOM.
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',loadCompanion,{once:true});
else loadCompanion();
