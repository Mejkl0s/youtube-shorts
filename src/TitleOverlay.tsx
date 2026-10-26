import type {CSSProperties} from 'react';
import {fontFamily,type Layout} from './template';

export default function TitleOverlay({title,layout}:{title:string;layout:Layout}){
  const style=layout.title_style??'outline';
  const decoration:CSSProperties=style==='outline'?{WebkitTextStroke:'.6cqw #000',paintOrder:'stroke fill'}:style==='shadow'?{textShadow:'.3cqw .4cqw .2cqw #000d'}:style==='box'?{background:'#000a',boxShadow:'0 0 0 1cqw #000a',borderRadius:'.8cqw'}:{};
  const colors=new Map((layout.title_highlights??[]).map(item=>[item.word.toLowerCase(),item.color]));
  return <h3 className={`title-theme-${style}`} style={{fontFamily:fontFamily(!layout.title_font||layout.title_font==='inherit'?layout.font:layout.title_font),top:`${layout.title_y*100}%`,fontSize:`${layout.title_size*100}cqw`,color:`#${layout.title_color}`,textAlign:layout.title_align??'center',left:`${layout.title_align==='left'?layout.title_x*100:5}%`,right:`${layout.title_align==='right'?layout.title_x*100:5}%`,letterSpacing:0,lineHeight:1.17,textShadow:'none',WebkitTextStroke:0,...decoration}}>{title.split(/(\s+)/u).map((part,index)=>/\S/u.test(part)?<span key={index} data-title-word={part} style={{color:colors.has(part.toLowerCase())?'#'+colors.get(part.toLowerCase()):undefined}}>{part}</span>:part)}</h3>;
}
