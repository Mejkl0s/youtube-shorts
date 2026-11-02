import React,{useRef,useState} from 'react';
import {Download,Upload} from 'lucide-react';
import {collectState,restoreState,openSavedState,flushDesktop,desktopAPI} from './desktop';

export default function ProjectExchange({save,disabled}:{save:()=>void;disabled:boolean}){
  const input=useRef<HTMLInputElement>(null),[busy,setBusy]=useState(false),[importing,setImporting]=useState(false),[message,setMessage]=useState('');
  async function exportProject(){
    setBusy(true);setMessage('Připravuji projekt včetně uložených videí…');save();
    try{
      if(window.rankDesktop){await flushDesktop();const result=await window.rankDesktop.exportProject(collectState());setMessage(result.saved?'Projekt exportován.':'Export zrušen.');}
      else{
        const response=await fetch('/api/project-exchange/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state:collectState()})});
        const result=await response.json();if(!response.ok)throw Error(result.detail||'Export selhal.');
        const link=document.createElement('a');link.href=result.url;link.download='Rank-Studio-projekt.rankstudio';link.click();setMessage('Archiv obsahuje projekt a dostupná média. Uložené klíče a cookies se neexportují.');
      }
    }catch(error){setMessage((error as Error).message);}finally{setBusy(false);}
  }
  async function applyImported(state:Record<string,string>){
    const current=collectState();
    if(window.rankDesktop)await desktopAPI('/projects',{state:current});
    else localStorage.setItem('rank-studio-project-before-import',JSON.stringify(current));
    await openSavedState(state);
  }
  async function importProject(file?:File){
    if(!confirm('Otevřít importovaný projekt? Současný uložený stav zůstane v záloze.'))return;
    setBusy(true);setImporting(true);setMessage('Kontroluji projekt a média…');save();let reloading=false;
    try{
      if(window.rankDesktop){const result=await window.rankDesktop.importProject();if(result.state){await applyImported(result.state);reloading=true;}}
      else if(file){
        const body=new FormData();body.append('file',file);
        const response=await fetch('/api/project-exchange/import',{method:'POST',body});const result=await response.json();
        if(!response.ok)throw Error(result.detail||'Import selhal.');await applyImported(result.state);reloading=true;
      }
    }catch(error){setMessage((error as Error).message);}finally{if(!reloading){setBusy(false);setImporting(false);}}
  }
  return <div className="project-exchange"><button className="text-button" disabled={disabled||busy} onClick={exportProject}><Download size={13}/>Export projektu</button><button className="text-button" disabled={disabled||busy} onClick={()=>window.rankDesktop?importProject():input.current?.click()}><Upload size={13}/>Import projektu</button><input type="file" accept=".rankstudio,.zip" hidden ref={input} onChange={event=>{const file=event.target.files?.[0];if(file)importProject(file);}}/>{!window.rankDesktop&&localStorage.getItem('rank-studio-project-before-import')&&<button className="text-button" disabled={disabled||busy} onClick={()=>{restoreState(JSON.parse(localStorage.getItem('rank-studio-project-before-import')!));localStorage.removeItem('rank-studio-project-before-import');location.reload();}}>Vrátit projekt před importem</button>}{message&&<small role="status">{message}</small>}{importing&&<div className="project-import-progress" role="status"><div><strong>Importuji projekt</strong><p>{message}</p><small>Po ověření se otevře přenesený projekt. Původní stav zůstane v záloze.</small></div></div>}</div>;
}
