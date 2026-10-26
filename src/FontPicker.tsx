import {useEffect,useId,useMemo,useRef,useState} from 'react';
import {ChevronDown,Search} from 'lucide-react';
import {FONT_CATALOG,fontFamily,type FontKey} from './template';

type Props={value:FontKey|'inherit';onChange:(value:FontKey|'inherit')=>void;label:string;disabled?:boolean;allowInherit?:boolean;inheritFont?:FontKey};

export default function FontPicker(p:Props){
  const [open,setOpen]=useState(false);
  const [query,setQuery]=useState('');
  const [active,setActive]=useState(0);
  const root=useRef<HTMLDivElement>(null);
  const trigger=useRef<HTMLButtonElement>(null);
  const search=useRef<HTMLInputElement>(null);
  const listId=useId();
  const all=useMemo(()=>[...(p.allowInherit?[{id:'inherit',label:'Podle šablony',note:'Použít písmo šablony'}]:[]),...FONT_CATALOG],[p.allowInherit]);
  const choices=all.filter(item=>`${item.label} ${item.note}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const selected=all.find(item=>item.id===p.value);
  const face=(value:string)=>fontFamily(value==='inherit'?(p.inheritFont??'bold'):value as FontKey);
  const choose=(value:string)=>{p.onChange(value as FontKey|'inherit');setOpen(false);trigger.current?.focus();};
  function show(){setQuery('');setActive(Math.max(0,all.findIndex(item=>item.id===p.value)));setOpen(true);}
  useEffect(()=>{if(p.disabled)setOpen(false);},[p.disabled]);
  useEffect(()=>{
    if(!open)return;
    search.current?.focus();
    const outside=(event:MouseEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener('mousedown',outside);
    return()=>document.removeEventListener('mousedown',outside);
  },[open]);
  useEffect(()=>{if(open)root.current?.querySelector(`[data-font-index="${active}"]`)?.scrollIntoView({block:'nearest'});},[open,active]);
  return <div className="font-picker" ref={root} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget))setOpen(false);}} onKeyDown={event=>{
    if(event.key==='Escape'){setOpen(false);trigger.current?.focus();return;}
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){
      event.preventDefault();
      if(!open){show();return;}
      setActive(old=>choices.length?(old+(event.key==='ArrowDown'?1:-1)+choices.length)%choices.length:0);
    }
    if(event.key==='Enter'&&open&&event.target===search.current){event.preventDefault();if(choices[active])choose(choices[active].id);}
  }}>
    <button ref={trigger} type="button" className="font-picker-trigger" data-font={p.value} role="combobox" aria-label={p.label} aria-haspopup="listbox" aria-expanded={open} aria-controls={listId} disabled={p.disabled} onClick={()=>open?setOpen(false):show()} title={selected?.note?`${selected.label} · ${selected.note}`:selected?.label}><span style={{fontFamily:face(p.value)}}>{selected?.label??'Vybrat písmo'}</span><ChevronDown size={13}/></button>
    {open&&<div className="font-picker-popup"><div className="font-search"><Search size={13}/><input ref={search} aria-label="Hledat písmo" placeholder="Hledat písmo…" value={query} onChange={event=>{setQuery(event.target.value);setActive(0);}} aria-controls={listId} aria-activedescendant={choices[active]?`${listId}-${active}`:undefined}/></div><div className="font-picker-options" role="listbox" aria-label="Dostupná písma" id={listId}>{choices.map((item,index)=><button type="button" key={item.id} id={`${listId}-${index}`} role="option" aria-label={item.label} aria-description={item.note||undefined} aria-selected={p.value===item.id} className={active===index?'focused':''} data-font-index={index} onMouseEnter={()=>setActive(index)} onClick={()=>choose(item.id)}><span className="font-option-name" style={{fontFamily:face(item.id)}}>{item.label}</span>{item.note&&<small>{item.note}</small>}</button>)}{!choices.length&&<p className="font-no-results">Žádné písmo neodpovídá hledání.</p>}</div></div>}
    <span className="font-picker-sample" style={{fontFamily:face(p.value)}} aria-hidden="true">AaBb · Žluťoučký · 123</span>
  </div>;
}
