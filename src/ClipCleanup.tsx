import {useEffect,useRef,useState} from 'react';

export type BlurRegion={x:number;y:number;w:number;h:number;origin?:'auto'|'manual';method?:'blur'|'remove';allow_large?:boolean;kind?:'text'|'emoji'|'logo'|'block'|'other'};
type Source={framing?:'fit'|'fill';id:string;url:string;start:number;duration:number;blur_regions?:BlurRegion[]};

export function safeBlurRegions(regions:BlurRegion[]=[]){
  let area=0;
  return regions.filter(r=>{const explicit=(r.origin??'manual')==='manual'&&r.allow_large;const size=r.w*r.h;if(!explicit&&(r.w>.9||r.h>.075||size>.04||r.kind==='block'||area+size>.085+1e-8))return false;if(!explicit)area+=size;return true;});
}

export function BlurMasks({regions=[]}:{regions?:BlurRegion[]}){
  return <div className="source-cleanup-masks" aria-hidden="true">{safeBlurRegions(regions).map((r,i)=><span key={i} style={{left:`${r.x*100}%`,top:`${r.y*100}%`,width:`${r.w*100}%`,height:`${r.h*100}%`,backdropFilter:`blur(max(8px,${r.h*89}cqw))`,WebkitBackdropFilter:`blur(max(8px,${r.h*89}cqw))`}}/>)}</div>;
}

export default function ClipCleanup({clip,rank,onClose,onApply,detect}:{clip:Source;rank:number;onClose:()=>void;onApply:(regions:BlurRegion[])=>void;detect:()=>Promise<{regions:BlurRegion[];message:string}>}){
  const [regions,setRegions]=useState(clip.blur_regions??[]);
  const [draft,setDraft]=useState<BlurRegion|null>(null);
  const [message,setMessage]=useState('Přetažením označ celý nápis včetně emoji, samostatné emoji, logo nebo rušivý blok. U oblasti zvol rozmazání nebo doplnění okolím.');
  const [busy,setBusy]=useState(false);
  const anchor=useRef<{x:number;y:number}|null>(null);
  const screen=useRef<HTMLDivElement>(null);
  const video=useRef<HTMLVideoElement>(null);
  useEffect(()=>{const onKey=(e:KeyboardEvent)=>{if(e.key==='Escape'&&!busy)onClose();};document.addEventListener('keydown',onKey);return()=>document.removeEventListener('keydown',onKey);},[busy,onClose]);
  const point=(e:React.PointerEvent)=>{const r=screen.current!.getBoundingClientRect();return{x:Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),y:Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))};};
  const rectangle=(e:React.PointerEvent)=>{const a=anchor.current!,b=point(e);return{x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),w:Math.abs(a.x-b.x),h:Math.abs(a.y-b.y),origin:'manual' as const,method:'blur' as const};};
  async function detectText(){
    setBusy(true);
    try{
      const found=await detect();
      setRegions(old=>[...old.filter(r=>r.origin!=='auto'),...found.regions].slice(0,8));
      setMessage(found.message);
    }catch(error){setMessage((error as Error).message);}
    finally{setBusy(false);}
  }
  return <div className="cleanup-backdrop"><section className="cleanup-dialog" role="dialog" aria-modal="true" aria-label={`Rozmazání klipu ${rank}`}>
    <header><h2>Čištění obrazu · klip #{rank}</h2><button autoFocus disabled={busy} onClick={onClose} aria-label="Zavřít rozmazání">×</button></header>
    <div className="cleanup-body"><div className="cleanup-screen" ref={screen}
      onPointerDown={e=>{if(busy||regions.length>=8||e.button!==0)return;e.currentTarget.setPointerCapture(e.pointerId);anchor.current=point(e);setDraft(null);}}
      onPointerMove={e=>{if(anchor.current)setDraft(rectangle(e));}}
      onPointerUp={e=>{if(!anchor.current)return;const box=rectangle(e);anchor.current=null;setDraft(null);if(box.w>=.01&&box.h>=.01)setRegions(old=>[...old,box].slice(0,8));}}
      onPointerCancel={()=>{anchor.current=null;setDraft(null);}}>
      <video ref={video} src={clip.url} style={{objectFit:clip.framing==='fit'?'contain':'cover'}} muted playsInline onLoadedMetadata={()=>{if(video.current)video.current.currentTime=clip.start+Math.min(.2,clip.duration/2);}}/>
      <BlurMasks regions={regions}/>
      {regions.map((r,i)=><button className="cleanup-region" key={i} aria-label={`Odebrat rozmazání ${i+1}`} disabled={busy} style={{left:`${r.x*100}%`,top:`${r.y*100}%`,width:`${r.w*100}%`,height:`${r.h*100}%`}} onPointerDown={e=>e.stopPropagation()} onClick={()=>setRegions(old=>old.filter((_,index)=>index!==i))}><span>{i+1} ×</span></button>)}
      {draft&&<div className="cleanup-draft" style={{left:`${draft.x*100}%`,top:`${draft.y*100}%`,width:`${draft.w*100}%`,height:`${draft.h*100}%`}}/>}
    </div><div className="cleanup-controls">{safeBlurRegions(regions).length<regions.length&&<p role="alert">Příliš velké masky jsou vypnuté. Odeber je a nech znovu najít pouze nápisy.</p>}<p role="status">{message}</p><p>Masky překrývají původní obraz. Vlastní nadpis, čísla a titulky zůstanou ostré. Odstranění doplní plochu z okolí; skrytý obraz se neobnoví. Hotový výsledek ověř v MP4, pracovní náhled ukazuje rozmazání.</p>
      <label>Snímek klipu<input aria-label="Snímek pro kontrolu rozmazání" type="range" min={clip.start} max={clip.start+clip.duration-.05} step="0.05" defaultValue={clip.start+.2} onChange={e=>{if(video.current)video.current.currentTime=Number(e.target.value);}}/></label>
      <button disabled={busy} onClick={detectText}>{busy?'Hledám překryvy…':'Najít nápisy, emoji a malá loga'}</button>
      <div className="cleanup-methods">{regions.map((r,i)=><div key={i}>Oblast {i+1}<select aria-label={`Úprava oblasti ${i+1}`} value={r.method??'blur'} disabled={busy} onChange={e=>setRegions(old=>old.map((box,n)=>n===i?{...box,method:e.target.value as 'blur'|'remove'}:box))}><option value="blur">Rozmazat</option><option value="remove">Odstranit · doplnit okolím</option></select><button type="button" aria-label={`Zvětšit oblast ${i+1}`} disabled={busy} onClick={()=>setRegions(old=>old.map((box,n)=>{if(n!==i)return box;const x=Math.max(0,box.x-.012),y=Math.max(0,box.y-.008);return {...box,x,y,w:Math.min(1,box.x+box.w+.012)-x,h:Math.min(1,box.y+box.h+.008)-y};}))}>Zvětšit okraje</button>{(r.origin??'manual')==='manual'&&<label><input type="checkbox" aria-label={`Povolit velkou ruční oblast ${i+1}`} checked={!!r.allow_large} onChange={e=>setRegions(old=>old.map((box,n)=>n===i?{...box,allow_large:e.target.checked}:box))}/>Výslovně povolit velkou ruční oblast</label>}</div>)}</div>
      <button disabled={busy||!regions.length} onClick={()=>setRegions([])}>Odebrat všechna rozmazání</button><small>{regions.length}/8 oblastí · kliknutím na oblast ji odebereš</small>
      <button className="primary-button" disabled={busy} onClick={()=>onApply(regions)}>Použít úpravy obrazu</button>
    </div></div>
  </section></div>;
}
