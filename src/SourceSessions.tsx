import {useEffect,useState} from 'react';
import {ChevronDown,ExternalLink,KeyRound,LoaderCircle,Trash2,Upload} from 'lucide-react';
import './sources.css';

type State={configured:boolean;cookie_count:number};
type Provider='tiktok'|'instagram';
const SOURCES:[Provider,string,string][]=[['tiktok','TikTok','https://www.tiktok.com/login'],['instagram','Instagram','https://www.instagram.com/accounts/login/']];

export default function SourceSessions({disabled,onError,local=false}:{disabled:boolean;onError:(message:string)=>void;local?:boolean}){
  const [sessions,setSessions]=useState<Partial<Record<Provider,State>>>({});
  const [busy,setBusy]=useState<Provider|null>(null);
  const [loaded,setLoaded]=useState(false);
  useEffect(()=>{fetch('/api/source-sessions').then(async r=>{if(!r.ok)throw Error('Stav přihlášených relací se nepodařilo načíst.');setSessions(await r.json());setLoaded(true);}).catch(e=>onError(e.message));},[]);
  async function update(provider:Provider,file?:File){
    if(file&&file.size>256*1024){onError('Soubor cookies může mít nejvýše 256 KB.');return;}
    setBusy(provider);
    try{
      const form=new FormData();if(file)form.append('file',file);
      const response=await fetch('/api/source-sessions/'+provider,{method:file?'POST':'DELETE',body:file?form:undefined});
      const result=await response.json();
      if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'Relaci se nepodařilo uložit.');
      setSessions(old=>({...old,[provider]:result}));
    }catch(e){onError((e as Error).message);}finally{setBusy(null);}
  }
  return <details className="source-sessions"><summary><KeyRound size={13}/>Přihlášení ke zdrojům · volitelné<ChevronDown size={13}/></summary><div className="source-session-body">
    <p>Přihlaš se na sociální síti ve svém prohlížeči. Pro použití ve studiu nahraj export své relace jako <strong>cookies.txt (Netscape)</strong>. Samotné otevření přihlášení relaci do studia nepřenese.{local?' Soubor zůstává v aplikaci na tvém počítači.':''}</p>
    <div className="source-session-grid">{SOURCES.map(([provider,name,url])=><div className="source-session-card" key={provider}>
      <div><strong>{name}</strong><span className={sessions[provider]?.configured?'session-ready':''}>{!loaded?'Načítání…':sessions[provider]?.configured?'Relace nahraná · stažení ji ověří':'Bez uložené relace'}</span></div>
      <a href={url} target="_blank" rel="noreferrer">Otevřít přihlášení<ExternalLink size={11}/></a>
      <div className="source-session-actions"><label className="button secondary">{busy===provider?<LoaderCircle size={12} className="spin"/>:<Upload size={12}/>}Nahrát cookies.txt<input type="file" aria-label={`Cookies pro ${name}`} accept=".txt,text/plain" disabled={disabled||!!busy} onChange={e=>{const file=e.target.files?.[0];if(file)update(provider,file);e.target.value='';}}/></label><button className="button secondary" aria-label={`Odpojit ${name}`} title="Odstranit uloženou relaci" disabled={disabled||!!busy||!sessions[provider]?.configured} onClick={()=>update(provider)}><Trash2 size={12}/></button></div>
    </div>)}</div>
    <p className="source-session-note">Cookies umožňují přístup k účtu: importuj jen vlastní relaci a neposílej soubor do chatu. Ukládá se pro vybranou síť. Uložení nezaručuje stažení; síť může odmítnout i přihlášený počítač.{local?' Nahrané klipy a relace z Renderu se sem automaticky nepřenášejí.':' Po restartu bezplatného Renderu může být nutné relaci znovu nahrát.'}</p>
  </div></details>;
}
