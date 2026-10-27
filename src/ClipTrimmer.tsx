import {useEffect,useRef,useState} from 'react';

type Context={source:{url:string;duration?:number};bounds:{start:number;end:number};current:{start:number;end:number};message:string};
export type Framing='fit'|'fill';
export default function ClipTrimmer({context,framing,onClose,onApply,onExpand}:{context:Context;framing:Framing;onExpand?:()=>void;onClose:()=>void;onApply:(start:number,end:number,framing:Framing)=>Promise<void>}){
  const [start,setStart]=useState(context.current.start);
  const [end,setEnd]=useState(context.current.end);
  const [frame,setFrame]=useState(framing);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const video=useRef<HTMLVideoElement>(null);
  const rangePlayback=useRef(false);
  useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.key==='Escape'&&!busy)onClose();};document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key);},[busy,onClose]);
  function changeStart(value:number){const v=Math.max(context.bounds.start,Math.min(context.bounds.end-2,value));setStart(v);setEnd(e=>Math.min(context.bounds.end,Math.max(v+2,Math.min(v+30,e))));if(video.current)video.current.currentTime=v;}
  function changeEnd(value:number){setEnd(Math.max(start+2,Math.min(context.bounds.end,start+30,value)));}
  async function save(){setBusy(true);setError('');try{await onApply(start,end,frame);}catch(e){setError((e as Error).message);setBusy(false);}}
  return <div className="cleanup-backdrop"><section className="cleanup-dialog trim-dialog" role="dialog" aria-modal="true" aria-label="Upravit střih a pointu">
    <header><h2>Upravit střih a pointu</h2><button autoFocus disabled={busy} onClick={onClose} aria-label="Zavřít úpravu střihu">×</button></header>
    <p>{context.message}</p>
    <video ref={video} src={context.source.url} controls playsInline onLoadedMetadata={()=>{if(video.current)video.current.currentTime=start;}} onTimeUpdate={()=>{if(rangePlayback.current&&video.current&&video.current.currentTime>=end){video.current.pause();rangePlayback.current=false;}}}/>
    <div className="trim-inputs"><label>Začátek (s)<input aria-label="Začátek výřezu" type="number" step="0.1" min={context.bounds.start} max={context.bounds.end-2} value={Number(start.toFixed(2))} disabled={busy} onChange={e=>changeStart(Number(e.target.value))}/><input aria-label="Posunout začátek výřezu" type="range" step="0.1" min={context.bounds.start} max={context.bounds.end-2} value={start} disabled={busy} onChange={e=>changeStart(Number(e.target.value))}/></label>
    <label>Konec (s)<input aria-label="Konec výřezu" type="number" step="0.1" min={start+2} max={Math.min(context.bounds.end,start+30)} value={Number(end.toFixed(2))} disabled={busy} onChange={e=>changeEnd(Number(e.target.value))}/><input aria-label="Posunout konec výřezu" type="range" step="0.1" min={start+2} max={Math.min(context.bounds.end,start+30)} value={end} disabled={busy} onChange={e=>changeEnd(Number(e.target.value))}/></label></div>
    <p>Délka: <strong>{(end-start).toFixed(1)} s</strong> · Nech prostor před hlavním momentem i po něm.</p>
    <label className="trim-framing">Obraz ve výsledném videu<select aria-label="Ořez obrazu" value={frame} disabled={busy} onChange={e=>setFrame(e.target.value as Framing)}><option value="fit">Celý obraz · zachovat děj u okrajů</option><option value="fill">Vyplnit 9:16 · oříznout okraje</option></select></label>
    <div className="trim-actions">{onExpand&&(context.bounds.start>0||context.bounds.end<(context.source.duration??0))&&<button disabled={busy} onClick={onExpand}>Celý původní zdroj</button>}<button disabled={busy} onClick={()=>{if(video.current){rangePlayback.current=true;video.current.currentTime=start;video.current.play().catch(e=>setError(e.message));}}}>Přehrát vybraný úsek</button><button disabled={busy||context.bounds.end-context.bounds.start>30} onClick={()=>{setStart(context.bounds.start);setEnd(context.bounds.end);}}>Celá scéna</button><button className="primary-button" disabled={busy||end-start<2||end-start>30} onClick={save}>{busy?'Připravuji výřez…':'Použít střih'}</button></div>
    {error&&<p role="alert">{error}</p>}
  </section></div>;
}
