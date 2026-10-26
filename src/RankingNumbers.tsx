import {rankMarkers,type Layout} from './template';

export default function RankingNumbers({layout,activeRank}:{layout:Layout;activeRank:number}){
  const column=layout.rank_display!=='single';
  return <div className={`${column?'phone-ranking-column':'phone-ranking-single'}${layout.rank_palette!=='custom'?' rank-medals':''}`} role="list" aria-label={column?'Pořadí 1 až 5':'Aktuální pořadí'}>
    {rankMarkers(layout,activeRank).map(marker=><div key={marker.rank} role="listitem" data-rank={marker.rank} aria-current={marker.active?'true':undefined} className={`phone-rank rank-${layout.rank_style??'outline'}${marker.active?' active':''}`} style={{top:`${marker.y*100}%`,left:`${layout.rank_x*100}%`,fontSize:`${marker.size*100}cqw`,color:`#${marker.color}${marker.alpha<1?'B8':''}`}}>{marker.text}</div>)}
  </div>;
}
