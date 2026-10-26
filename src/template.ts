import FONT_CATALOG from '../backend/fonts/catalog.json';
export {FONT_CATALOG};
export type FontKey='bold'|'condensed'|'serif'|'arial-compatible'|'times-compatible'|'calibri-compatible'|'anton'|'bebas-neue'|'poppins'|'lato'|'archivo-black'|'barlow-condensed';
export type TitleHighlight={word:string;color:string};
export type Layout = {
  font:FontKey; title_font:'inherit'|FontKey; title_color:string; title_style:'outline'|'shadow'|'plain'|'box'; title_highlights:TitleHighlight[]; rank_color:string; rank_palette:'medals'|'custom'; caption_color:string;
  title_y:number; title_size:number; title_align:'left'|'center'|'right'; title_x:number;
  rank_x:number; rank_y:number; rank_size:number; rank_style:'outline'|'badge'|'plain'; rank_display:'column'|'single'; caption_y:number; caption_size:number;
  caption_align:'left'|'center'|'right'; caption_x:number; header_darkness:number; show_label:boolean; show_criteria:boolean;
};
export type Reference = {id:string;name:string;url:string;analyzed:boolean;layout?:Layout;notes:string;kind?:'image'|'video';duration?:number;frame_time?:number;instructions?:string;analysis_mode?:'free'|'ai'|'manual';detected?:string[]};
export const DEFAULT_LAYOUT:Layout = {font:'bold',title_font:'inherit',title_color:'FFFFFF',title_style:'outline',title_highlights:[],rank_palette:'medals',rank_color:'CAFA63',caption_color:'FFFFFF',title_y:.0615,title_size:.0454,title_align:'center',title_x:.05,rank_x:.0602,rank_y:.1719,rank_size:.1343,rank_style:'outline',rank_display:'column',caption_y:.7708,caption_size:.0528,caption_align:'center',caption_x:.07,header_darkness:.5,show_label:false,show_criteria:false};
export const RANKING_LAYOUT:Layout = {...DEFAULT_LAYOUT,font:'condensed',rank_color:'FFD84D',rank_size:.18,rank_x:.05,title_y:.045,title_size:.062,caption_size:.063,caption_y:.79,header_darkness:.65,rank_display:'single'};
export const COLUMN_LAYOUT:Layout = {...RANKING_LAYOUT,rank_display:'column',rank_size:.1,rank_y:.2};

export const fontFamily=(font:FontKey)=>{const entry=FONT_CATALOG.find(item=>item.id===font)??FONT_CATALOG[0];return `${entry.css_family},${entry.category==='serif'?'Georgia,serif':'Arial,sans-serif'}`;};

export const MEDAL_COLORS:Record<number,string>={1:'FFD34E',2:'C5CBD3',3:'CD965D',4:'FFFFFF',5:'FFFFFF'};

export function rankMarkers(layout:Layout,activeRank:number){
  const paint=(rank:number)=>layout.rank_palette!=='custom'?{color:MEDAL_COLORS[rank],alpha:1}:{color:rank===activeRank?layout.rank_color:'FFFFFF',alpha:rank===activeRank?1:.72};
  if(layout.rank_display==='single')return [{rank:activeRank,text:`#${activeRank}`,y:layout.rank_y,size:layout.rank_size,active:true,...paint(activeRank),alpha:1}];
  const gap=Math.min(.12,(.88-layout.rank_y)/4.8);
  const size=Math.min(layout.rank_size,.115,gap*16/9*.8);
  return Array.from({length:5},(_,i)=>({rank:i+1,text:`${i+1}.`,y:layout.rank_y+i*gap,size,active:i+1===activeRank,...paint(i+1)}));
}
