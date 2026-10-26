import type {Layout} from './template';

type Props={layout:Layout;onLayout:(layout:Layout)=>void;followTopic:boolean;onFollowTopic:(follow:boolean)=>void;width:number;disabled:boolean};

export default function TitleSettings(p:Props){
  return <fieldset className="title-settings" aria-label="Vzhled nadpisu" disabled={p.disabled}>
    <label className="title-follow"><input type="checkbox" checked={p.followTopic} onChange={e=>p.onFollowTopic(e.target.checked)}/>Přebírat nadpis z „Co dnes rankujeme?“</label>
    <div className="title-style-row"><label>Písmo nadpisu<select aria-label="Písmo nadpisu" value={p.layout.title_font??'inherit'} onChange={e=>p.onLayout({...p.layout,title_font:e.target.value as Layout['title_font']})}><option value="inherit">Podle šablony</option><option value="bold">Tučné</option><option value="condensed">Úzké tučné</option><option value="serif">Patkové</option></select></label><label>Barva nadpisu ve videu<input aria-label="Barva nadpisu ve videu" type="color" value={`#${p.layout.title_color}`} onChange={e=>p.onLayout({...p.layout,title_color:e.target.value.slice(1).toUpperCase()})}/></label></div>
    <label className="title-size"><span>Velikost nadpisu<output>{Math.round(p.layout.title_size*p.width)} px</output></span><input aria-label="Velikost nadpisu" type="range" min={Math.ceil(p.width*.02)} max={Math.floor(p.width*.085)} step={1} value={Math.round(p.layout.title_size*p.width)} onChange={e=>p.onLayout({...p.layout,title_size:Number(e.target.value)/p.width})}/></label>
  </fieldset>;
}
