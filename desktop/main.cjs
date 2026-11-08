'use strict';
const {app,BrowserWindow,Tray,Menu,ipcMain,dialog,shell,session}=require('electron');
const {spawn}=require('node:child_process');
const crypto=require('node:crypto');
const fs=require('node:fs');
const fsp=require('node:fs/promises');
const path=require('node:path');
const {Readable}=require('node:stream');
const {pipeline}=require('node:stream/promises');
const {trustedSender,stateInput,externalURL,preferences}=require('./security.cjs');
const {createUpdates}=require('./updates.cjs');
const {localFetch}=require('./transport.cjs');

app.setName('Rank Studio');
app.setAppUserModelId('cz.rankstudio.desktop');
const userDirectory=process.env.RANK_DESKTOP_TEST_DATA&&!app.isPackaged?process.env.RANK_DESKTOP_TEST_DATA:path.join(app.getPath('appData'),'Rank Studio');
fs.mkdirSync(userDirectory,{recursive:true});app.setPath('userData',userDirectory);
const privateToken=crypto.randomBytes(32).toString('hex'),adminToken=crypto.randomBytes(32).toString('hex');
let window,tray,backend,origin='',quitting=false,quitPending=false,updateInstall=false,updates;
let stderrTail='',settings={closeBehavior:'quit',minimizeToTray:false,startAtLogin:false,language:'cs',autoCheckUpdates:false};
let selectedModel='Model není vybraný';
const flushWaiters=new Map();
const dataDirectory=()=>app.getPath('userData');
const settingsPath=()=>path.join(dataDirectory(),'desktop-preferences.json');
function writeSettings(){
  const temporary=settingsPath()+'.tmp';fs.mkdirSync(dataDirectory(),{recursive:true});
  fs.writeFileSync(temporary,JSON.stringify(settings));fs.renameSync(temporary,settingsPath());
}
async function api(route,{method='GET',body,admin=false,signal}={}){
  if(!origin)throw Error('Místní backend ještě není připravený.');
  const response=await localFetch(origin+route,{method,signal:signal||AbortSignal.timeout(30000),redirect:'error',
    headers:{'X-Rank-Desktop-Token':privateToken,...(admin?{'X-Rank-Desktop-Admin':adminToken}:{}),...(body!==undefined?{'Content-Type':'application/json'}:{})},
    body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.ok){let message='Operace místní aplikace selhala.';try{const data=await response.json();if(typeof data.detail==='string')message=data.detail;}catch{}throw Error(message);}
  return response.json();
}
function handle(channel,fn){
  ipcMain.handle(channel,async(event,...args)=>{
    if(!trustedSender(event,origin))throw Error('Nepovolené desktopové okno.');
    return fn(...args);
  });
}
function bindIPC(){
  handle('app:info',()=>({version:app.getVersion(),platform:process.platform,dataDirectory:dataDirectory(),settings:{...settings},updates:updates.status(),packaged:app.isPackaged}));
  handle('app:preferences',value=>{settings=preferences(value);writeSettings();if(process.platform==='win32')app.setLoginItemSettings({openAtLogin:settings.startAtLogin});return {...settings};});
  handle('state:load',()=>api('/api/desktop/state'));
  handle('state:save',state=>api('/api/desktop/state',{method:'POST',body:{state:stateInput(state)}}));
  handle('projects:export',async state=>{
    stateInput(state);
    const chosen=await dialog.showSaveDialog(window,{title:'Export projektu včetně videí',defaultPath:'Rank-Studio-projekt.rankstudio',filters:[{name:'Rank Studio projekt',extensions:['rankstudio']}]});
    if(chosen.canceled||!chosen.filePath)return {cancelled:true};
    const result=await api('/api/project-exchange/export',{method:'POST',body:{state},signal:AbortSignal.timeout(300000)});
    const response=await localFetch(origin+result.url,{headers:{'X-Rank-Desktop-Token':privateToken},redirect:'error',signal:AbortSignal.timeout(300000)});
    if(!response.ok||!response.body)throw Error('Archiv projektu není dostupný.');
    const temporary=chosen.filePath+'.partial-'+crypto.randomUUID();
    try{await pipeline(Readable.fromWeb(response.body),fs.createWriteStream(temporary,{flags:'wx'}));await fsp.rename(temporary,chosen.filePath);}
    finally{await fsp.rm(temporary,{force:true});}
    return {saved:true};
  });
  handle('projects:import',async()=>{
    const chosen=await dialog.showOpenDialog(window,{title:'Import projektu',properties:['openFile'],filters:[{name:'Rank Studio projekt',extensions:['rankstudio','zip']}]});
    if(chosen.canceled||!chosen.filePaths[0])return {cancelled:true};
    const selected=chosen.filePaths[0];if((await fsp.stat(selected)).size>8*1024**3)throw Error('Projekt překračuje limit 8 GB.');
    const form=new FormData();form.append('file',await fs.openAsBlob(selected),path.basename(selected));
    const response=await localFetch(origin+'/api/project-exchange/import',{method:'POST',headers:{'X-Rank-Desktop-Token':privateToken},body:form,redirect:'error',signal:AbortSignal.timeout(300000)});
    const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'Import selhal.');
    return result;
  });
  async function chooseDirectory(title,route){
    const chosen=await dialog.showOpenDialog(window,{title,properties:['openDirectory','createDirectory']});
    if(chosen.canceled||!chosen.filePaths[0])return {cancelled:true};
    return api(route,{method:'POST',admin:true,body:{directory:chosen.filePaths[0]},signal:AbortSignal.timeout(600000)});
  }
  handle('storage:migrate',()=>chooseDirectory('Vyber původní složku Rank Studia','/api/desktop/migrate'));
  handle('models:storage',()=>chooseDirectory('Úložiště modelů pro Ollama spuštěnou aplikací','/api/desktop/models/storage'));
  handle('app:open-data',()=>shell.openPath(dataDirectory()));
  handle('app:open-link',value=>shell.openExternal(externalURL(value)));
  handle('updates:check',()=>updates.check());handle('updates:download',()=>updates.download());
  handle('updates:install',async()=>{if(updates.status().status!=='ready')throw Error('Aktualizace ještě není připravená.');updateInstall=true;await requestQuit();return {restarting:quitting};});
  handle('app:quit',async()=>{await requestQuit();return {quitting};});
  ipcMain.on('desktop:flushed',(event,id,ok)=>{if(trustedSender(event,origin)&&flushWaiters.has(id)){flushWaiters.get(id)(ok===true);flushWaiters.delete(id);}});
}
async function flushRenderer(){
  if(!window||window.isDestroyed()||!origin)return true;
  const id=crypto.randomUUID();
  return new Promise(resolve=>{
    const timer=setTimeout(()=>{flushWaiters.delete(id);resolve(false);},7000);
    flushWaiters.set(id,ok=>{clearTimeout(timer);resolve(ok);});window.webContents.send('desktop:before-quit',id);
  });
}
async function stopBackend(){
  if(!backend||backend.exitCode!==null)return;
  try{await api('/api/desktop/shutdown',{method:'POST',body:{},admin:true,signal:AbortSignal.timeout(10000)});}catch{}
  const child=backend;
  if(child.exitCode!==null)return;
  await Promise.race([new Promise(resolve=>child.once('exit',resolve)),new Promise(resolve=>setTimeout(resolve,10000))]);
  if(child.exitCode===null){
    // The PID is always our own direct child, never a discovered server.
    if(process.platform==='win32')await new Promise(resolve=>{const killer=spawn('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true});killer.once('exit',resolve);killer.once('error',resolve);});
    else{try{process.kill(-child.pid,'SIGKILL');}catch{try{child.kill('SIGKILL');}catch{}}}
  }
}
async function requestQuit(){
  if(quitPending||quitting)return;quitPending=true;
  try{
    let activity={jobs:[]};try{activity=await api('/api/desktop/activity');}catch{}
    if(activity.jobs.length){const result=await dialog.showMessageBox(window,{type:'question',title:'Probíhají úlohy',message:'Ukončit aplikaci a zastavit běžící úlohy?',buttons:['Vrátit se','Zastavit a ukončit'],defaultId:0,cancelId:0});if(result.response!==1){updateInstall=false;return;}}
    if(!await flushRenderer()){
      const result=await dialog.showMessageBox(window,{type:'warning',title:'Uložení projektu se nepodařilo',message:'Poslední změny se nepodařilo potvrdit. Vrať se do editoru, nebo ukonči bez jejich uložení.',buttons:['Vrátit se','Ukončit bez uložení'],defaultId:0,cancelId:0});if(result.response!==1){updateInstall=false;return;}
    }
    quitting=true;await stopBackend();if(tray)tray.destroy();
    if(updateInstall)updates.install();else app.quit();
  }finally{quitPending=false;}
}
function reveal(){if(window&&!window.isDestroyed()){window.show();window.focus();}}
function trayMenu(){
  tray?.setContextMenu(Menu.buildFromTemplate([
    {label:'Otevřít Rank Studio',click:reveal},{label:selectedModel,enabled:false},
    {label:'Zastavit úlohy / pozastavit stahování',click:()=>api('/api/desktop/cancel-all',{method:'POST',body:{}}).catch(()=>{})},
    {label:'Nastavení',click:()=>{reveal();window.webContents.send('desktop:open-settings');}},
    {type:'separator'},{label:'Ukončit',click:requestQuit}
  ]));
}
async function startBackend(){
  const packaged=app.isPackaged;
  const override=!packaged&&process.env.RANK_DESKTOP_BACKEND;
  const command=override||(packaged?path.join(process.resourcesPath,'backend',process.platform==='win32'?'rank-backend.exe':'rank-backend'):
    process.env.RANK_DESKTOP_PYTHON||path.resolve(__dirname,'..','.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python'));
  const args=packaged||override?[]:[path.resolve(__dirname,'../scripts/desktop_backend.py')];
  const inherited=Object.fromEntries(Object.entries(process.env).filter(([key])=>!/(?:API_KEY|TOKEN|PASSWORD|SECRET|CSC_LINK)$/i.test(key)&&!['NODE_OPTIONS','ELECTRON_RUN_AS_NODE'].includes(key)));
  const environment={...inherited,RANK_DATA_DIR:path.join(dataDirectory(),'runtime'),RANK_DESKTOP_TOKEN:privateToken,RANK_DESKTOP_ADMIN_TOKEN:adminToken,
    PYTHONUTF8:'1',PYTHONUNBUFFERED:'1',RANK_DESKTOP_PARENT_PID:String(process.pid)};
  backend=spawn(command,args,{env:environment,windowsHide:true,detached:process.platform!=='win32',stdio:['ignore','pipe','pipe']});
  backend.stderr.on('data',chunk=>{stderrTail=(stderrTail+String(chunk)).slice(-12000);});
  await new Promise((resolve,reject)=>{
    let buffer='';const timer=setTimeout(()=>reject(Error('Místní backend neodpověděl do 90 sekund.')),90000);
    backend.once('error',()=>{clearTimeout(timer);reject(Error('Nepodařilo se spustit přibalený backend.'));});
    backend.once('exit',()=>{clearTimeout(timer);if(!origin)reject(Error('Backend se zastavil při spouštění. '+stderrTail));else if(!quitting){dialog.showErrorBox('Rank Studio','Místní backend se neočekávaně zastavil. Projekt zůstává v datovém adresáři.');}});
    backend.stdout.on('data',chunk=>{
      buffer+=String(chunk);
      const lines=buffer.split('\n');buffer=lines.pop();
      for(const line of lines){
        if(line.startsWith('RANK_STUDIO_READY=')){
          try{const port=JSON.parse(line.slice('RANK_STUDIO_READY='.length)).port;if(!Number.isInteger(port)||port<1||port>65535)throw Error();origin=`http://127.0.0.1:${port}`;clearTimeout(timer);resolve();}
          catch{clearTimeout(timer);reject(Error('Backend předal neplatnou adresu.'));}
        }
      }
    });
  });
  for(let attempt=0;attempt<150;attempt++){
    try{const health=await api('/api/health',{signal:AbortSignal.timeout(2000)});if(health.desktop&&health.studio==='rank-studio')return;}
    catch{}
    if(backend.exitCode!==null)throw Error('Místní backend se zastavil.');
    await new Promise(resolve=>setTimeout(resolve,200));
  }
  throw Error('Místní editor se nepřipravil v časovém limitu.');
}
async function run(){
  if(!app.requestSingleInstanceLock()){app.quit();return;}
  app.on('second-instance',reveal);
  app.on('before-quit',event=>{if(!quitting){event.preventDefault();requestQuit();}});
  await app.whenReady();
  fs.mkdirSync(dataDirectory(),{recursive:true});
  if(fs.existsSync(settingsPath()))settings=preferences(JSON.parse(fs.readFileSync(settingsPath(),'utf8')));
  updates=createUpdates(app);bindIPC();Menu.setApplicationMenu(null);
  window=new BrowserWindow({width:1440,height:960,minWidth:900,minHeight:650,show:false,backgroundColor:'#060607',title:'Rank Studio',
    icon:path.join(__dirname,'assets/icon.png'),webPreferences:{preload:path.join(__dirname,'preload.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,allowRunningInsecureContent:false,partition:'persist:rank-studio'}});
  const ownSession=window.webContents.session;
  await ownSession.setProxy({mode:'direct'});
  ownSession.setPermissionRequestHandler((_webContents,_permission,callback)=>callback(false));
  ownSession.setPermissionCheckHandler(()=>false);
  ownSession.webRequest.onBeforeSendHeaders((details,callback)=>{
    const headers={...details.requestHeaders};
    // A renderer can neither choose nor leak our main-only administrative token.
    for(const key of Object.keys(headers))if(key.toLowerCase().startsWith('x-rank-desktop-'))delete headers[key];
    if(origin&&new URL(details.url).origin===origin)headers['X-Rank-Desktop-Token']=privateToken;
    callback({requestHeaders:headers});
  });
  window.webContents.on('will-navigate',(event,url)=>{if(!origin||new URL(url).origin!==origin)event.preventDefault();});
  window.webContents.setWindowOpenHandler(({url})=>{try{shell.openExternal(externalURL(url));}catch{}return {action:'deny'};});
  window.webContents.on('will-attach-webview',event=>event.preventDefault());
  window.on('close',event=>{if(quitting)return;event.preventDefault();if(settings.closeBehavior==='tray')window.hide();else requestQuit();});
  window.on('minimize',()=>{if(settings.minimizeToTray)window.hide();});
  // The loading page needs no file:// privileges. Reading its trusted ASAR
  // resource in main also works with the hardened file-protocol fuse disabled.
  await window.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent(fs.readFileSync(path.join(__dirname,'loading.html'),'utf8')));window.show();
  tray=new Tray(path.join(__dirname,'assets/icon.png'));tray.setToolTip('Rank Studio');tray.on('double-click',reveal);trayMenu();
  ownSession.on('will-download',(event,item)=>{
    if(!origin||!item.getURL().startsWith(origin+'/api/')){event.preventDefault();return;}
    // Pause until the native Save As dialog returns; keep renderer file access narrow.
    const selected=dialog.showSaveDialogSync(window,{defaultPath:item.getFilename(),title:'Uložit soubor'});
    if(!selected)item.cancel();else item.setSavePath(selected);
  });
  await startBackend();await window.loadURL(origin);
  const refreshModel=async()=>{try{const config=await api('/api/desktop/ai/config');selectedModel=(config.providers[config.active.provider]?.name||'AI')+' · '+(config.active.model||'Nevybrán');trayMenu();}catch{}};
  await refreshModel();const timer=setInterval(refreshModel,15000);timer.unref();
  if(settings.autoCheckUpdates)updates.check().catch(()=>{});
  // Test-only automation is never enabled in a packaged build.
  if(!app.isPackaged&&process.env.RANK_DESKTOP_SMOKE==='1'){
    setTimeout(async()=>{
      try{
        const result=await window.webContents.executeJavaScript(`JSON.stringify({title:document.title,desktop:!!window.rankDesktop,node:typeof require,root:!!document.querySelector('main')})`);
        console.log('DESKTOP_SMOKE='+result);
      }finally{quitting=true;await stopBackend();app.quit();}
    },2000);
  }
}
run().catch(async error=>{quitting=true;await stopBackend();dialog.showErrorBox('Rank Studio se nepodařilo spustit',String(error.message).slice(0,12000));app.exit(1);});
