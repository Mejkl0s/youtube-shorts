'use strict';
const fs=require('node:fs');
const path=require('node:path');
function createUpdates(app,onChange=()=>{}){
  let state={status:'disabled',message:'Distribuce podepsaných aktualizací není nakonfigurovaná.'},updater;
  const set=patch=>{state={...state,...patch};onChange(state);return state;};
  try{
    const policy=JSON.parse(fs.readFileSync(path.join(__dirname,'update-policy.json'),'utf8'));
    if(app.isPackaged&&process.platform==='win32'&&policy.enabled&&typeof policy.publisher==='string'&&policy.publisher.trim()&&new URL(policy.url).protocol==='https:'){
      const {NsisUpdater}=require('electron-updater');
      updater=new NsisUpdater({provider:'generic',url:policy.url,publisherName:[policy.publisher]});
      // Require our publisher even if app-update.yml is missing or incomplete.
      const {verifySignature}=require('electron-updater/out/windowsExecutableCodeSignatureVerifier');
      updater.verifySignature=file=>verifySignature([policy.publisher],file,updater._logger);
      updater.autoDownload=false;updater.autoInstallOnAppQuit=false;updater.allowDowngrade=false;
      // The default NSIS verifier runs Windows Authenticode and checks publisherName.
      updater.on('checking-for-update',()=>set({status:'checking',message:'Ověřuji nové vydání…'}));
      updater.on('update-available',info=>set({status:'available',version:info.version,notes:typeof info.releaseNotes==='string'?info.releaseNotes:'',message:'Je dostupná nová verze.'}));
      updater.on('update-not-available',()=>set({status:'current',message:'Používáš aktuální vydání.'}));
      updater.on('download-progress',progress=>set({status:'downloading',percent:Math.round(progress.percent),message:'Stahuji a ověřuji podepsanou aktualizaci…'}));
      updater.on('update-downloaded',()=>set({status:'ready',message:'Aktualizace ověřena. Instalace vyžaduje restart aplikace.'}));
      updater.on('error',()=>set({status:'error',message:'Aktualizaci nelze ověřit nebo stáhnout. Instalace byla zastavena.'}));
      set({status:'idle',message:'Podepsané aktualizace jsou připravené ke kontrole.'});
    }
  }catch{/* No feed, no signature policy: never enable an insecure fallback. */}
  return {status:()=>({...state}),async check(){if(updater)await updater.checkForUpdates();return {...state};},
    async download(){if(!updater||state.status!=='available')throw Error('Nejdřív ověř dostupnost vydání.');await updater.downloadUpdate();return {...state};},
    install(){if(!updater||state.status!=='ready')throw Error('Aktualizace nebyla ověřena.');updater.quitAndInstall(false,true);}};
}
module.exports={createUpdates};
