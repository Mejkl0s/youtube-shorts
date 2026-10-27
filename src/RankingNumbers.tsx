import {useLayoutEffect,useRef} from 'react';
import {rankMarkers,type Layout} from './template';

function Note({text,font}:{text:string;font:string}){
  const ref=useRef<HTMLSpanElement>(null);
  useLayoutEffect(()=>{
    const el=ref.current!;
    const fit=()=>{el.style.fontSize='3.2cqw';const size=parseFloat(getComputedStyle(el).fontSize);if(el.scrollWidth>el.clientWidth)el.style.fontSize=`${Math.max(1,size*el.clientWidth/el.scrollWidth)}px`;};
    const observer=new ResizeObserver(fit);observer.observe(el.parentElement!);fit();
    let active=true;document.fonts.ready.then(()=>{if(active)fit();});
    return()=>{active=false;observer.disconnect();};
  },[text,font]);
  return <span ref={ref} className="phone-rank-note">{text}</span>;
}

export default function RankingNumbers({layout,activeRank,notes={}}:{layout:Layout;activeRank:number;notes?:Record<number,string>}){
  const column=layout.rank_display!=='single';
  return <div className={`${column?'phone-ranking-column':'phone-ranking-single'}${layout.rank_palette!=='custom'?' rank-medals':''}`} role="list" aria-label={column?'Pořadí 1 až 5':'Aktuální pořadí'}>
    {rankMarkers(layout,activeRank).map(marker=><div className="phone-rank-row" role="listitem" key={marker.rank} style={{top:`${marker.y*100}%`,left:`${layout.rank_x*100}%`}}>
      <div data-rank={marker.rank} aria-current={marker.active?'true':undefined} className={`phone-rank rank-${layout.rank_style??'outline'}${marker.active?' active':''}`} style={{top:`${marker.y*100}%`,left:`${layout.rank_x*100}%`,fontSize:`${marker.size*100}cqw`,color:`#${marker.color}${marker.alpha<1?'B8':''}`}}>{marker.text}</div>
      {notes[marker.rank]&&<Note text={notes[marker.rank]} font={layout.font}/>}
    </div>)}
  </div>;
}
