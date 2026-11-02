export type DesktopPreferences={closeBehavior:'quit'|'tray';minimizeToTray:boolean;startAtLogin:boolean;language:string;autoCheckUpdates:boolean};
export type UpdateState={status:string;message:string;version?:string;notes?:string;percent?:number};
export type DesktopInfo={version:string;platform:string;packaged:boolean;dataDirectory:string;settings:DesktopPreferences;updates:UpdateState};
export type SavedState=Record<string,string>;
type ImportResult={cancelled?:boolean;state?:SavedState;message?:string};
export type DesktopBridge={
  info:()=>Promise<DesktopInfo>;preferences:(value:DesktopPreferences)=>Promise<DesktopPreferences>;
  loadState:()=>Promise<{state:SavedState}>;saveState:(state:SavedState)=>Promise<unknown>;
  exportProject:(state:SavedState)=>Promise<{cancelled?:boolean;saved?:boolean}>;importProject:()=>Promise<ImportResult>;
  migrate:()=>Promise<{message?:string;cancelled?:boolean}>;modelDirectory:()=>Promise<{message?:string;cancelled?:boolean}>;
  openData:()=>Promise<unknown>;openLink:(url:string)=>Promise<unknown>;
  checkUpdates:()=>Promise<UpdateState>;downloadUpdate:()=>Promise<UpdateState>;installUpdate:()=>Promise<unknown>;quit:()=>Promise<unknown>;
  onSettings:(callback:()=>void)=>()=>void;onBeforeQuit:(callback:()=>Promise<unknown>)=>()=>void;
};
declare global{interface Window{rankDesktop?:DesktopBridge;}}
export const STATE_KEYS=['rank-studio-project','rank-studio-chat','rank-studio-assets','rank-studio-sources','rank-studio-previous-clips','rank-studio-writing'];
let restoring=false;
export const restoringState=()=>restoring;
export function collectState():SavedState{
  return Object.fromEntries(STATE_KEYS.map(key=>[key,localStorage.getItem(key)]).filter((row):row is [string,string]=>row[1]!==null));
}
export function restoreState(state:SavedState){
  restoring=true;
  for(const key of STATE_KEYS){if(typeof state[key]==='string')localStorage.setItem(key,state[key]);else localStorage.removeItem(key);}
}
export async function desktopAPI<T>(path:string,body?:unknown):Promise<T>{
  const response=await fetch('/api/desktop'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?undefined:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Operace se nepodařila.');return data;
}
let pending:ReturnType<typeof setTimeout>|undefined;
let saving:Promise<unknown>=Promise.resolve();
export function flushDesktop(){
  if(!restoring)window.dispatchEvent(new Event('rank-desktop-save-current'));
  clearTimeout(pending);const state=collectState();
  saving=saving.catch(()=>{}).then(()=>window.rankDesktop?.saveState(state));return saving;
}
export async function openSavedState(state:SavedState){
  if(!window.rankDesktop){restoreState(state);location.reload();return;}
  await flushDesktop();restoring=true;clearTimeout(pending);
  // Commit the target before replacing browser state. A failed database write
  // leaves the current editor and autosave usable; its saved copy is retained.
  try{saving=saving.catch(()=>{}).then(()=>window.rankDesktop!.saveState(state));await saving;}
  catch(error){restoring=false;throw error;}
  location.reload();
}
export async function bootstrapDesktop(){
  if(!window.rankDesktop)return;
  const {state}=await window.rankDesktop.loadState();restoreState(state);restoring=false;
  const changed=()=>{if(restoring)return;clearTimeout(pending);pending=setTimeout(()=>flushDesktop().catch(()=>window.dispatchEvent(new Event('rank-desktop-storage-error'))),500);};
  const set=Storage.prototype.setItem,remove=Storage.prototype.removeItem;
  Storage.prototype.setItem=function(key,value){set.call(this,key,value);if(this===localStorage&&STATE_KEYS.includes(key))changed();};
  Storage.prototype.removeItem=function(key){remove.call(this,key);if(this===localStorage&&STATE_KEYS.includes(key))changed();};
  window.rankDesktop.onBeforeQuit(flushDesktop);
}
