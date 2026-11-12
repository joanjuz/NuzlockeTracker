'use strict';
// Run profiles selector and dialogs.
// Named runs keep all UI state fresh by reloading after the backend swaps services.
async function profileRequest(payload){
  const response=await fetch('/api/profiles',payload?{method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify(payload)}:{});
  const result=await response.json();
  if(!response.ok)throw Error(result.error||'No se pudo abrir la partida.');
  return result;
}
async function selectRunProfile(ident){
  const select=$('run-profile'),previous=select.dataset.active;
  select.disabled=true;$('new-run-profile').disabled=true;
  try{
    await profileRequest({action:'select',id:ident});
    window.location.reload();
  }catch(error){
    select.value=previous;
    $('status').textContent=error.message;
    throw error;
  }finally{select.disabled=false;$('new-run-profile').disabled=false;}
}
async function loadRunProfiles(known){
  try{
    const result=known||await profileRequest(),select=$('run-profile');
    select.replaceChildren(...result.profiles.map(profile=>new Option(profile.name,profile.id)));
    select.value=result.active;select.dataset.active=result.active;
    $('run-profile-controls').hidden=false;
    configureProfileDeletion(result);
    // Unsaved level-cap stages are never discarded by switching runs without asking.
    select.onchange=async()=>{
      if(typeof confirmLevelCapsLeave==='function'&&!(await confirmLevelCapsLeave())){select.value=select.dataset.active;return;}
      selectRunProfile(select.value).catch(()=>{});
    };
    $('new-run-profile').onclick=async()=>{
      if(typeof confirmLevelCapsLeave==='function'&&!(await confirmLevelCapsLeave()))return;
      $('run-profile-feedback').textContent='';
      $('run-profile-name').value='';
      $('run-profile-dialog').showModal();$('run-profile-name').focus();
    };
    $('run-profile-close').onclick=()=>$('run-profile-dialog').close();
    $('run-profile-form').onsubmit=async event=>{
      event.preventDefault();
      const button=$('run-profile-create'),name=$('run-profile-name').value.trim();
      if(!name){$('run-profile-feedback').textContent='Escribe un nombre para la partida.';return;}
      button.disabled=true;$('run-profile-close').disabled=true;
      $('run-profile-feedback').textContent='Creando partida…';
      try{
        const created=await profileRequest({action:'create',name});
        // Keep a newly created run accessible even if switching must be retried.
        await loadRunProfiles();
        await selectRunProfile(created.created);
      }catch(error){$('run-profile-feedback').textContent=error.message;}
      finally{button.disabled=false;$('run-profile-close').disabled=false;}
    };
  }catch(error){$('run-profile-controls').hidden=true;}
}
function configureProfileDeletion(result){
  const open=$('delete-run-profile');if(!open)return;
  open.onclick=()=>{
    const options=result.profiles.map(profile=>{
      const option=new Option(profile.name,profile.id);
      option.disabled=profile.id===result.active;
      return option;
    });
    const picker=$('delete-run-profile-select');picker.replaceChildren(...options);
    const available=result.profiles.filter(profile=>profile.id!==result.active);
    picker.value=available[0]?.id||'';
    const check=()=>{$('delete-run-profile-confirm').disabled=!available.some(profile=>profile.id===picker.value);};
    picker.onchange=check;check();
    $('delete-run-profile-feedback').textContent=available.length?'':'Abre otra partida para poder eliminar la actual.';
    $('delete-run-profile-dialog').showModal();
  };
  $('delete-run-profile-close').onclick=()=>$('delete-run-profile-dialog').close();
  $('delete-run-profile-confirm').onclick=()=>deleteRunProfile($('delete-run-profile-select').value,result);
}
async function deleteRunProfile(ident,result){
  const profile=result.profiles.find(profile=>profile.id===ident),feedback=$('delete-run-profile-feedback');
  if(!profile||ident===result.active){feedback.textContent='No se puede eliminar la partida abierta. Abre otra partida primero.';return;}
  const button=$('delete-run-profile-confirm');button.disabled=true;$('delete-run-profile-select').disabled=true;$('delete-run-profile-close').disabled=true;
  try{
    const updated=await profileRequest({action:'delete',id:ident});
    await loadRunProfiles(updated);$('delete-run-profile-dialog').close();
    $('status').textContent='Partida «'+profile.name+'» eliminada.';
  }catch(error){feedback.textContent=error.message;}
  finally{button.disabled=false;$('delete-run-profile-select').disabled=false;$('delete-run-profile-close').disabled=false;}
}
// End named run controls.
