import {MEDAL_COLORS,type Layout} from './template';

export default function RankSettings({layout,onLayout,disabled}:{layout:Layout;onLayout:(value:Layout)=>void;disabled:boolean}){
  return <fieldset className="rank-appearance" disabled={disabled}>
    <legend>Čísla a poznámky</legend>
    <label>Barvy čísel<select aria-label="Barevný režim čísel" value={layout.rank_palette??'medals'} onChange={e=>onLayout({...layout,rank_palette:e.target.value as Layout['rank_palette']})}>
      <option value="medals">Medailové barvy</option><option value="custom">Vlastní barva aktuálního čísla</option><option value="individual">Vlastní barva každého čísla</option>
    </select></label>
    {layout.rank_palette==='custom'?<label>Aktuální číslo<input aria-label="Barva aktuálního čísla" type="color" value={'#'+layout.rank_color} onChange={e=>onLayout({...layout,rank_color:e.target.value.slice(1).toUpperCase()})}/></label>:<div className="individual-rank-colors">{[1,2,3,4,5].map(rank=><label key={rank}>#{rank}<input type="color" aria-label={`Barva čísla ${rank}`} value={'#'+(layout.rank_palette==='individual'?layout.rank_colors?.[rank]??MEDAL_COLORS[rank]:MEDAL_COLORS[rank])} onChange={e=>onLayout({...layout,rank_palette:'individual',rank_colors:{...MEDAL_COLORS,...layout.rank_colors,[rank]:e.target.value.slice(1).toUpperCase()}})}/></label>)}</div>}
    <label className="note-animation-option"><input type="checkbox" aria-label="Animovat nástup poznámek" checked={layout.note_animation!==false} onChange={e=>onLayout({...layout,note_animation:e.target.checked})}/>Animovat nástup poznámek</label>
    <p>Poznámka se objeví u svého klipu a zůstane do konce žebříčku.</p>
  </fieldset>;
}
