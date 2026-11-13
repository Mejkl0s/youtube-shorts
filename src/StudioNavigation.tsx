import type {ReactNode} from 'react';
import {AudioLines,Clapperboard,FolderOpen,Layers3,Search,Sparkles} from 'lucide-react';

export const STUDIO_TABS=[
  {id:'search',label:'Hledání',title:'Najít klipy',description:'Zadej téma a vyber momenty pro svůj Short.',icon:Search},
  {id:'clips',label:'Klipy',title:'Klipy a střih',description:'Pořadí, hlavní momenty a poznámky ke klipům.',icon:Clapperboard},
  {id:'appearance',label:'Vzhled',title:'Vzhled videa',description:'Nadpis, čísla a tvoje předloha.',icon:Layers3},
  {id:'sound',label:'Zvuk',title:'Zvuk a efekty',description:'Hlas, efekty a vyvážení zvukových stop.',icon:AudioLines},
  {id:'project',label:'Projekt',title:'Tvůj projekt',description:'Uložení a přenos rozpracovaného Shortu.',icon:FolderOpen},
  {id:'ai',label:'AI',title:'AI a modely',description:'Uložený výběr modelu a textový pomocník.',icon:Sparkles},
] as const;
export type StudioTab=typeof STUDIO_TABS[number]['id'];

export default function StudioNavigation({active,onSelect,ready}:{active:StudioTab;onSelect:(tab:StudioTab)=>void;ready:number}){
  return <nav className="studio-navigation" role="tablist" aria-label="Sekce studia" aria-orientation="vertical">
    {STUDIO_TABS.map(({id,label,icon:Icon},index)=><button key={id} id={`studio-tab-${id}`} role="tab" type="button"
      aria-label={label} aria-selected={active===id} aria-controls={`studio-panel-${id}`} tabIndex={active===id?0:-1}
      className={`rail-button studio-nav-button ${active===id?'active':''}`} title={label} onClick={()=>onSelect(id)}
      onKeyDown={event=>{
        let next:number;
        if(event.key==='ArrowDown'||event.key==='ArrowRight')next=(index+1)%STUDIO_TABS.length;
        else if(event.key==='ArrowUp'||event.key==='ArrowLeft')next=(index+STUDIO_TABS.length-1)%STUDIO_TABS.length;
        else if(event.key==='Home')next=0;
        else if(event.key==='End')next=STUDIO_TABS.length-1;
        else return;
        event.preventDefault();const tab=STUDIO_TABS[next].id;onSelect(tab);
        document.getElementById(`studio-tab-${tab}`)?.focus();
      }}><Icon size={19}/><span className="studio-nav-label">{label}</span>{id==='clips'&&<small aria-hidden="true">{ready}/5</small>}</button>)}
  </nav>;
}

export function StudioPanel({id,active,children}:{id:StudioTab;active:StudioTab;children:ReactNode}){
  return <section id={`studio-panel-${id}`} className="studio-panel" role="tabpanel" aria-labelledby={`studio-tab-${id}`} hidden={active!==id} tabIndex={0}>{children}</section>;
}
