'use strict';
const {contextBridge,ipcRenderer}=require('electron');
const invoke=(channel,...args)=>ipcRenderer.invoke(channel,...args);
contextBridge.exposeInMainWorld('rankDesktop',Object.freeze({
  info:()=>invoke('app:info'),preferences:value=>invoke('app:preferences',value),
  loadState:()=>invoke('state:load'),saveState:value=>invoke('state:save',value),
  exportProject:value=>invoke('projects:export',value),importProject:()=>invoke('projects:import'),
  migrate:()=>invoke('storage:migrate'),modelDirectory:()=>invoke('models:storage'),
  openData:()=>invoke('app:open-data'),openLink:value=>invoke('app:open-link',value),
  checkUpdates:()=>invoke('updates:check'),downloadUpdate:()=>invoke('updates:download'),installUpdate:()=>invoke('updates:install'),
  quit:()=>invoke('app:quit'),
  onSettings:callback=>{const handler=()=>callback();ipcRenderer.on('desktop:open-settings',handler);return()=>ipcRenderer.removeListener('desktop:open-settings',handler);},
  onBeforeQuit:callback=>{const handler=async(_event,id)=>{try{await callback();ipcRenderer.send('desktop:flushed',id,true);}catch{ipcRenderer.send('desktop:flushed',id,false);}};ipcRenderer.on('desktop:before-quit',handler);return()=>ipcRenderer.removeListener('desktop:before-quit',handler);}
}));
