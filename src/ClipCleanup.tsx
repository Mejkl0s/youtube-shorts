import {useEffect,useRef,useState} from 'react';

export type BlurRegion={x:number;y:number;w:number;h:number;origin?:'auto'|'manual';method?:'blur'|'remove';kind?:'text'|'logo'|'block'|'other'};
type Source={framing?:'fit'|'fill';id:string;url:string;start:number;duration:number;blur_regions?:BlurRegion[]};

export function BlurMasks({regions=[]}:{regions?:BlurRegion[]}){
  return <div className="source-cleanup-masks" aria-hidden="true">{regions.map((r,i)=><span key={i} style={{left:`${r.x*100}%`,top:`${r.y*100}%`,width:`${r.w*100}%`,height:`${r.h*100}%`}}/>)}</div>;
}

export default function ClipCleanup({clip,rank,onClose,onApply,detect}:{clip:Source;rank:number;onClose:()=>void;onApply:(regions:BlurRegion[])=>void;detect:()=>Promise<{regions:BlurRegion[];message:string}>}){
  const [regions,setRegions]=useState(clip.blur_regions??[]);
  const [draft,setDraft]=useState<BlurRegion|null>(null);
  const [message,setMessage]=useState('Přetažením označ nápis, logo nebo rušivý blok. U oblasti zvol rozmazání nebo doplnění okolím.');
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
    </div><div className="cleanup-controls"><p role="status">{message}</p><p>Masky překrývají původní obraz. Vlastní nadpis, čísla a titulky zůstanou ostré. Odstranění doplní plochu z okolí; skrytý obraz se neobnoví. Hotový výsledek ověř v MP4, pracovní náhled ukazuje rozmazání.</p>
      <label>Snímek klipu<input aria-label="Snímek pro kontrolu rozmazání" type="range" min={clip.start} max={clip.start+clip.duration-.05} step="0.05" defaultValue={clip.start+.2} onChange={e=>{if(video.current)video.current.currentTime=Number(e.target.value);}}/></label>
      <button disabled={busy} onClick={detectText}>{busy?'Hledám překryvy…':'Najít nápisy, loga a bloky'}</button>
      <div className="cleanup-methods">{regions.map((r,i)=><label key={i}>Oblast {i+1}<select aria-label={`Úprava oblasti ${i+1}`} value={r.method??'blur'} disabled={busy} onChange={e=>setRegions(old=>old.map((box,n)=>n===i?{...box,method:e.target.value as 'blur'|'remove'}:box))}><option value="blur">Rozmazat</option><option value="remove">Odstranit · doplnit okolím</option></select></label>)}</div>
      <button disabled={busy||!regions.length} onClick={()=>setRegions([])}>Odebrat všechna rozmazání</button><small>{regions.length}/8 oblastí · kliknutím na oblast ji odebereš</small>
      <button className="primary-button" disabled={busy} onClick={()=>onApply(regions)}>Použít úpravy obrazu</button>
    </div></div>
  </section></div>;
}
