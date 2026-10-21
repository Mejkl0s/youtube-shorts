export type Layout = {
  font:'bold'|'condensed'|'serif'; title_color:string; rank_color:string; caption_color:string;
  title_y:number; title_size:number; title_align:'left'|'center'|'right'; title_x:number;
  rank_x:number; rank_y:number; rank_size:number; rank_style:'outline'|'badge'|'plain'; caption_y:number; caption_size:number;
  caption_align:'left'|'center'|'right'; caption_x:number; header_darkness:number; show_label:boolean; show_criteria:boolean;
};
export type Reference = {id:string;name:string;url:string;analyzed:boolean;layout?:Layout;notes:string;kind?:'image'|'video';duration?:number;frame_time?:number;instructions?:string;analysis_mode?:'free'|'ai'|'manual';detected?:string[]};
export const DEFAULT_LAYOUT:Layout = {font:'bold',title_color:'FFFFFF',rank_color:'CAFA63',caption_color:'FFFFFF',title_y:.0615,title_size:.0454,title_align:'center',title_x:.05,rank_x:.0602,rank_y:.1719,rank_size:.1343,rank_style:'outline',caption_y:.7708,caption_size:.0528,caption_align:'center',caption_x:.07,header_darkness:.5,show_label:false,show_criteria:false};
export const RANKING_LAYOUT:Layout = {...DEFAULT_LAYOUT,font:'condensed',rank_color:'FFD84D',rank_size:.18,rank_x:.05,title_y:.045,title_size:.062,caption_size:.063,caption_y:.79,header_darkness:.65};
