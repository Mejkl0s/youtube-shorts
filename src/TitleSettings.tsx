import {useState} from 'react';
import type {Layout} from './template';

type Props={title:string;layout:Layout;onLayout:(layout:Layout)=>void;followTopic:boolean;onFollowTopic:(follow:boolean)=>void;width:number;disabled:boolean};

export default function TitleSettings(p:Props){
  const [selected,setSelected]=useState('');
  const words=[...new Map((p.title.match(/\S+/gu)??[]).map(word=>[word.toLowerCase(),word])).values()];
  const selectedWord=words.find(word=>word.toLowerCase()===selected);
  const highlights=p.layout.title_highlights??[];
  const wordColor=(word:string)=>highlights.find(item=>item.word.toLowerCase()===word.toLowerCase())?.color;
  const paint=(word:string,color:string)=>p.onLayout({...p.layout,title_highlights:[...highlights.filter(item=>item.word.toLowerCase()!==word.toLowerCase()&&words.some(current=>current.toLowerCase()===item.word.toLowerCase())),{word,color}]});
  return <fieldset className="title-settings" aria-label="Vzhled nadpisu" disabled={p.disabled}>
    <label className="title-follow"><input type="checkbox" checked={p.followTopic} onChange={e=>p.onFollowTopic(e.target.checked)}/>Přebírat nadpis z „Co dnes rankujeme?“</label>
    <div className="title-style-row"><label>Písmo nadpisu<select aria-label="Písmo nadpisu" value={p.layout.title_font??'inherit'} onChange={e=>p.onLayout({...p.layout,title_font:e.target.value as Layout['title_font']})}><option value="inherit">Podle šablony</option><option value="bold">Tučné</option><option value="condensed">Úzké tučné</option><option value="serif">Patkové</option></select></label><label>Barva nadpisu ve videu<input aria-label="Barva nadpisu ve videu" type="color" value={`#${p.layout.title_color}`} onChange={e=>p.onLayout({...p.layout,title_color:e.target.value.slice(1).toUpperCase()})}/></label></div>
    <label className="title-size"><span>Velikost nadpisu<output>{Math.round(p.layout.title_size*p.width)} px</output></span><input aria-label="Velikost nadpisu" type="range" min={Math.ceil(p.width*.02)} max={Math.floor(p.width*.085)} step={1} value={Math.round(p.layout.title_size*p.width)} onChange={e=>p.onLayout({...p.layout,title_size:Number(e.target.value)/p.width})}/></label>
    <label className="title-theme-choice">Vzhled písma<select aria-label="Vzhled písma nadpisu" value={p.layout.title_style??'outline'} onChange={e=>p.onLayout({...p.layout,title_style:e.target.value as Layout['title_style']})}><option value="outline">Výrazná kontura</option><option value="shadow">Jemný stín</option><option value="plain">Čisté písmo</option><option value="box">Tmavý podklad</option></select></label>
    <div className="title-word-colors"><p>Klikni na slovo pro žluté zvýraznění, pak můžeš zvolit jinou barvu. Stejná slova se obarví stejně.</p><div className="title-word-buttons">{words.map(word=><button key={word.toLowerCase()} type="button" aria-label={`Obarvit slovo ${word}`} aria-pressed={word.toLowerCase()===selected} style={{color:'#'+(wordColor(word)??p.layout.title_color)}} onClick={()=>{setSelected(word.toLowerCase());if(!wordColor(word))paint(word,'FFD84D');}}>{word}</button>)}</div><div className="title-word-picker"><label>Barva vybraného slova<input type="color" aria-label="Barva vybraného slova" disabled={!selectedWord} value={'#'+(selectedWord?wordColor(selectedWord)??p.layout.title_color:p.layout.title_color)} onChange={e=>{if(selectedWord)paint(selectedWord,e.target.value.slice(1).toUpperCase());}}/></label><button className="text-button" type="button" disabled={!selectedWord||!wordColor(selectedWord)} onClick={()=>p.onLayout({...p.layout,title_highlights:highlights.filter(item=>item.word.toLowerCase()!==selected)})}>Vrátit základní barvu</button></div></div>
  </fieldset>;
}
