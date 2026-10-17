import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowDown, ArrowUp, ArrowUpRight, AudioLines, Check, ChevronDown, Clapperboard, Download, Film, FolderOpen, Info, Layers3, LoaderCircle, Mic2, MessageSquare, Paperclip, Send, Pause, Play, Plus, RotateCcw, Save, Search, Settings2, ShieldCheck, SlidersHorizontal, Sparkles, Trophy, Upload, Volume2, VolumeX, WandSparkles, X, Zap } from 'lucide-react';
import './styles.css';
import TemplatePanel from './TemplatePanel';
import {DEFAULT_LAYOUT,type Layout,type Reference} from './template';

type Clip = { id: string; name: string; title: string; voiceover: string; duration: number; sourceDuration: number; start: number; url: string; thumbnail: string; reason?: string; source_url?: string };
type VoiceSettings = { provider: 'openai'|'elevenlabs'|'piper'; voice: string; speed: number; delivery: string };
type ChatMessage = { id: string; role: 'user'|'assistant'; content: string; pending?: boolean };
const DEFAULT_VOICE: VoiceSettings = { provider:'openai', voice:'onyx', speed:1, delivery:'A confident, natural male narrator. Clear English, conversational energy, varied emphasis. No exaggerated shouting. Let the key observation land.' };
const VOICES = [{id:'openai:onyx',name:'Onyx · hlubší mužský',provider:'openai',voice:'onyx'}, {id:'openai:echo',name:'Echo · přirozený mužský',provider:'openai',voice:'echo'}, {id:'elevenlabs:adam',name:'Adam · ElevenLabs',provider:'elevenlabs',voice:'adam'}, {id:'elevenlabs:josh',name:'Josh · ElevenLabs',provider:'elevenlabs',voice:'josh'}, {id:'elevenlabs:antoni',name:'Antoni · ElevenLabs',provider:'elevenlabs',voice:'antoni'}, {id:'elevenlabs:custom',name:'Vlastní · ElevenLabs',provider:'elevenlabs',voice:'custom'}, {id:'piper:local',name:'Piper · lokální alternativa',provider:'piper',voice:'local'}] as const;
type AIProject = { topic:string; title:string; ranking_criteria:string; language:string; resolution:string; candidate_count:number; allow_youtube:boolean; voice:boolean; effects:boolean; captions:boolean; original_volume:number; voice_volume:number; effects_volume:number; layout:Layout; voice_settings:VoiceSettings; clips:Record<string,unknown>[] };
type Health = { voices: Record<string, boolean>; ai_scripts: boolean; elevenlabs: boolean; reference_voice: boolean; owner_login?:boolean };
type Job = { id: string; status: string; progress: number; message: string; download?: string; clips?: Record<string, unknown>[]; candidate_count?: number; kind?: string; mode?: 'free'|'ai'; search_results?: {url:string;title:string}[]; warnings?:string[]; assistant_reply?: string; project?: AIProject; reference?: Reference; research?: Research };
type Research = { channels: { name: string; url: string; observation: string; evidence: string }[]; recommendations: string[]; limitations: string };
const words = (text: string) => text.match(/[\p{L}\p{N}]+(?:['’\-][\p{L}\p{N}]+)*/gu)?.length ?? 0;
const blankClips = (): (Clip | null)[] => Array(5).fill(null);
const time = (n: number) => `${Math.floor(n / 60).toString().padStart(2, '0')}:${Math.floor(n % 60).toString().padStart(2, '0')}`;
const normalize = (a: Record<string, unknown>): Clip => ({ ...(a as unknown as Clip), title: String(a.title ?? a.name), voiceover: String(a.voiceover ?? ''), start: Number(a.start ?? 0), sourceDuration: Number(a.sourceDuration ?? a.duration), duration: a.start !== undefined ? Number(a.duration) : Math.min(4, Number(a.duration)) });

async function api<T>(path: string, data?: unknown, multipart = false): Promise<T> {
  const response = await fetch(`/api${path}`, { method: data === undefined ? 'GET' : 'POST', headers: multipart || data === undefined ? undefined : { 'Content-Type': 'application/json' }, body: data === undefined ? undefined : multipart ? data as FormData : JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) {
    const detail = result.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: { msg: string }) => d.msg).join(' ') : 'Požadavek se nezdařil.');
  }
  return result;
}

function App() {
  const [chatInput, setChatInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [reference, setReference] = useState<Reference | null>(null);
  const [templateMethod,setTemplateMethod]=useState<'free'|'ai'>('free');
  const [templateInstructions,setTemplateInstructions]=useState('');
  const [templateFrame,setTemplateFrame]=useState(0);
  const [layout, setLayout] = useState<Layout>(DEFAULT_LAYOUT);
  const [voiceSettings, setVoiceSettings] = useState<VoiceSettings>(DEFAULT_VOICE);
  const [clips, setClips] = useState<(Clip | null)[]>(blankClips);
  const [title, setTitle] = useState('TOP 5 UNEXPECTED MOMENTS');
  const [topic, setTopic] = useState('');
  const [criteria, setCriteria] = useState('Surprise, timing and skill');
  const [allowYoutube, setAllowYoutube] = useState(true);
  const [language, setLanguage] = useState('en');
  const [resolution, setResolution] = useState('1080');
  const [voice, setVoice] = useState(false);
  const [effects, setEffects] = useState(true);
  const [captions, setCaptions] = useState(true);
  const [originalVolume, setOriginalVolume] = useState(0.12);
  const [voiceVolume, setVoiceVolume] = useState(1);
  const [effectsVolume, setEffectsVolume] = useState(0.55);
  const [candidateCount, setCandidateCount] = useState(12);
  const [discoveryMode, setDiscoveryMode] = useState<'free'|'ai'>('free');
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState('');
  const [uploadIndex, setUploadIndex] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [health, setHealth] = useState<Health | null>(null);
  const [modal, setModal] = useState<'settings' | 'audio' | 'research' | null>(null);
  const [research, setResearch] = useState<Research | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [exported, setExported] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [restored, setRestored] = useState(false);
  const referenceInput = useRef<HTMLInputElement>(null);
  const chatLog = useRef<HTMLDivElement>(null);
  const assistantTurn = useRef<string|null>(null);
  const pendingDownload = useRef<string|null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const uploadTarget = useRef<number | null>(null);
  const voiceAudio = useRef<HTMLAudioElement | null>(null);
  const ready = clips.filter(Boolean).length;
  const current = clips[selected];
  const totalDuration = clips.reduce((sum, c) => sum + (c?.duration ?? 4), 0);
  const hasVoice = voiceSettings.provider==='openai' ? !!health?.ai_scripts : voiceSettings.provider==='elevenlabs' ? !!health?.elevenlabs : !!health?.voices[language];
  const occupied = !!busy || !!(job && !['done', 'failed'].includes(job.status));

  useEffect(() => {
    api<Health>('/health').then(h=>{setHealth(h);if(!h.ai_scripts)setTemplateMethod('free');}).catch(() => setError('Server není dostupný. Spusťte backend podle README.'));
    try {
      const savedProject = JSON.parse(localStorage.getItem('rank-studio-project') ?? 'null');
      if (savedProject?.clips?.length === 5) {
        setClips(savedProject.clips); setTitle(savedProject.title || 'TOP 5 MOMENTS'); setTopic(savedProject.topic || ''); setCriteria(savedProject.criteria || 'Surprise, timing and skill'); setLanguage(savedProject.language || 'en');
        setVoice(savedProject.voice ?? false); setEffects(savedProject.effects ?? true); setCaptions(savedProject.captions ?? true); setResolution(savedProject.resolution || '1080'); setDiscoveryMode(savedProject.discoveryMode==='ai'?'ai':'free');
        setAllowYoutube(savedProject.allowYoutube ?? true); setCandidateCount(savedProject.candidateCount || 12); setOriginalVolume(savedProject.originalVolume ?? 0.12); setVoiceVolume(savedProject.voiceVolume ?? 1); setEffectsVolume(savedProject.effectsVolume ?? 0.55);
        setLayout({...DEFAULT_LAYOUT,...savedProject.layout}); setVoiceSettings(savedProject.voiceSettings || DEFAULT_VOICE); setReference(savedProject.reference || null);setTemplateInstructions(savedProject.templateInstructions??savedProject.reference?.instructions??'');setTemplateFrame(savedProject.reference?.frame_time??0);setTemplateMethod(savedProject.templateMethod==='ai'?'ai':'free'); setRestored(true); setToast('Uložený projekt byl obnoven.');
      }
    } catch { localStorage.removeItem('rank-studio-project'); }
    try { const history=JSON.parse(localStorage.getItem('rank-studio-chat') || '[]'); if(Array.isArray(history))setMessages(history.slice(-30).filter(m=>['user','assistant'].includes(m.role)).map(m=>m.pending?{...m,pending:false,content:'Po obnovení nebyl výsledek tohoto příkazu ověřen. Zkontroluj projekt.'}:m)); } catch {}
    return () => { voiceAudio.current?.pause(); };
  }, []);
  useEffect(() => { setSaved(false); setExported(pendingDownload.current); pendingDownload.current=null; }, [clips, title, criteria, language, voice, effects, captions, resolution, originalVolume, voiceVolume, effectsVolume, layout, voiceSettings]);
  useEffect(()=>{try{localStorage.setItem('rank-studio-chat',JSON.stringify(messages.slice(-30)));}catch{} if(chatLog.current)chatLog.current.scrollTop=chatLog.current.scrollHeight;},[messages]);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(''), 5000); return () => clearTimeout(t); }, [toast]);
  useEffect(() => {
    if (!job || ['done', 'failed'].includes(job.status)) return;
    const interval = setInterval(async () => {
      try {
        const next = await api<Job>(`/jobs/${job.id}`);
        setJob(next);
        if(next.kind==='assistant' && next.assistant_reply && assistantTurn.current){setMessages(old=>old.map(m=>m.id===assistantTurn.current?{...m,content:next.assistant_reply!,pending:!['done','failed'].includes(next.status)}:m));}
        if(next.kind==='assistant' && ['done','failed'].includes(next.status)){if(next.project){pendingDownload.current=next.download || null;applyProject(next.project);}else if(next.download)setExported(next.download);if(next.reference){setReference(next.reference);setTemplateInstructions(next.reference.instructions??'');setTemplateFrame(next.reference.frame_time??0);}if(next.research){setResearch(next.research);setModal('research');}}
        if (next.status === 'failed') setError(next.message);
        if (next.status === 'done') {
          if (next.clips) { setClips(next.clips.map(normalize)); setSelected(0); if(next.mode==='free')setVoice(false); setToast(next.mode==='free'?`Vybráno pět scén z ${next.candidate_count} videí bez placeného API. Zkontroluj obsah a pořadí.`:`AI vybrala pět momentů z ${next.candidate_count} videí.`); }
          if (next.download && next.kind!=='assistant') { setExported(next.download); setToast('Export dokončen. Váš Short je připravený!'); }
        }
      } catch (e) { setError((e as Error).message); setJob(null); }
    }, 1000);
    return () => clearInterval(interval);
  }, [job?.id, job?.status]);
  useEffect(() => {
    const el = video.current;
    if (!el || !current) return;
    el.currentTime = current.start;
    if (playing) el.play().catch(() => setPlaying(false));
    else el.pause();
  }, [selected, current?.url]);
  useEffect(() => { if(video.current) video.current.volume = originalVolume; }, [originalVolume, current?.url]);
  useEffect(() => { if (playing && current) video.current?.play().catch(() => setPlaying(false)); else video.current?.pause(); }, [playing]);
  useEffect(() => {
    if (!modal) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setModal(null); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [modal]);

  function changeClip(index: number, changes: Partial<Clip>) {
    setClips(old => old.map((c, i) => i === index && c ? { ...c, ...changes } : c));
  }
  async function upload(files: FileList | File[], index: number | null) {
    if (occupied) return;
    const list = Array.from(files);
    const targets = index !== null ? [index] : clips.map((c, i) => c ? -1 : i).filter(i => i >= 0);
    if (!targets.length) { setError('Všech pět míst je obsazeno. Vyberte klip, který chcete nahradit.'); return; }
    setBusy('Nahrávám a připravuji videa…'); setError('');
    try {
      for (const [i, file] of list.slice(0, targets.length).entries()) {
        if (file.size > 300 * 1024 * 1024) throw new Error('Maximální velikost jednoho klipu je 300 MB.');
        setUploadIndex(targets[i]);
        const form = new FormData(); form.append('file', file);
        const result = await api<Record<string, unknown>>('/upload', form, true);
        setClips(old => old.map((c, slot) => slot === targets[i] ? normalize(result) : c));
      }
      setToast('Klipy jsou připravené. Doplňte krátký voiceover.');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(''); setUploadIndex(null); if (fileInput.current) fileInput.current.value = ''; }
  }
  function chooseFiles(index: number | null) { uploadTarget.current = index; fileInput.current?.click(); }
  async function loadDemo() {
    if (ready && !window.confirm('Nahradit aktuální klipy syntetickou ukázkou?')) return;
    setError(''); setBusy('Připravuji pět ukázkových klipů…');
    try { const result = await api<{ clips: Record<string, unknown>[] }>('/demo', {}); setClips(result.clips.map(normalize)); setTitle('TOP 5 COLOR REMIXES'); setSelected(0); setToast('Syntetická ukázka načtena. Nejde o klipy z TikToku.'); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(''); }
  }
  async function discover() {
    if (topic.trim().length < 3) { setError('Napište téma alespoň o třech znacích, například funny cats.'); return; }
    if (ready && !window.confirm('Nahradit aktuální klipy novým vyhledáváním?')) return;
    setError(''); setExported(null);
    try { const result = await api<Job>('/discover', { topic, ranking_criteria: criteria, source: 'social', allow_youtube: allowYoutube, language, candidate_count: candidateCount, mode:discoveryMode }); setJob(result); setTitle(`TOP 5 ${topic.toUpperCase()}`.slice(0, 70)); }
    catch (e) { setError((e as Error).message); if (discoveryMode==='ai' && !health?.ai_scripts) setModal('settings'); }
  }
  async function generateScripts() {
    if (ready !== 5) { setError('Nejdřív připravte všech pět klipů.'); return; }
    setBusy('AI píše krátké komentáře podle obrazu…'); setError('');
    try { const result = await api<{ lines: string[] }>('/scripts', { clips: clips.filter(Boolean), language, ranking_criteria: criteria }); setClips(old => old.map((c, i) => c ? { ...c, voiceover: result.lines[i] } : c)); setToast('Pět krátkých komentářů je připravených.'); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(''); }
  }
  async function playVoice(clip: Clip) {
    if (!clip.voiceover || words(clip.voiceover) > 7) { setError('Voiceover musí mít 1 až 7 slov.'); return; }
    setBusy('Připravuji ukázku hlasu…'); setError('');
    try { const result = await api<{ url: string }>('/voice-preview', { text: clip.voiceover, language, voice_settings: voiceSettings }); voiceAudio.current?.pause(); const audio = new Audio(result.url); voiceAudio.current = audio; await audio.play(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(''); }
  }
  async function exportVideo() {
    setError('');
    if (ready !== 5) { setError(`Připravte všech pět klipů. Zatím máte ${ready}/5.`); return; }
    if (!title.trim()) { setError('Doplňte název videa.'); return; }
    if (clips.some(c => c && (words(c.voiceover) > 7 || (voice && words(c.voiceover) === 0)))) { setError('Každý zapnutý voiceover musí mít 1 až 7 slov.'); return; }
    if (voice && !hasVoice) { setError('AI hlas zatím není dostupný. Otevřete nastavení hlasu; export bez hlasu lze ověřit jeho vypnutím.'); setModal('settings'); return; }
    try { setExported(null); setJob(await api<Job>('/render', { title, ranking_criteria: criteria, clips, language, voice, effects, captions, resolution, layout, voice_settings: voiceSettings, original_volume: originalVolume, voice_volume: voiceVolume, effects_volume: effectsVolume })); }
    catch (e) { setError((e as Error).message); }
  }
  async function doResearch() {
    setModal('research'); setBusy('Zkoumám ranking kanály na YouTube…'); setError('');
    try { setResearch(await api<Research>('/research', { topic: topic || 'ranking Shorts' })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(''); }
  }
  function saveProject() {
    try { localStorage.setItem('rank-studio-project', JSON.stringify({ clips, title, topic, criteria, allowYoutube, layout, voiceSettings, reference, language, voice, effects, captions, resolution, originalVolume, voiceVolume, effectsVolume, candidateCount, discoveryMode, templateMethod, templateInstructions })); setSaved(true); setRestored(true); setToast('Projekt uložen v tomto prohlížeči.'); }
    catch { setError('Prohlížeč nemohl projekt uložit.'); }
  }
  function resetProject() {
    if (ready && !window.confirm('Vymazat aktuální projekt? Nahrané soubory zůstanou na serveru.')) return;
    setClips(blankClips()); setDiscoveryMode('free');setVoice(false); setLayout(DEFAULT_LAYOUT);setVoiceSettings(DEFAULT_VOICE);setReference(null);setTemplateInstructions('');setTemplateFrame(0);setTemplateMethod('free');setMessages([]); setTopic(''); setCriteria('Surprise, timing and skill'); setTitle('TOP 5 UNEXPECTED MOMENTS'); setSelected(0); setPlaying(false); setElapsed(0); setJob(null); setExported(null); setError(''); localStorage.removeItem('rank-studio-project'); setRestored(false); setToast('Nový projekt je připravený.');
  }
  function moveClip(index: number, direction: number) {
    const target = index + direction;
    if (target < 0 || target > 4) return;
    setClips(old => { const next = [...old]; [next[index], next[target]] = [next[target], next[index]]; return next; });
    setSelected(target);
  }

  function applyProject(p:AIProject){
    setTopic(p.topic);setTitle(p.title);setCriteria(p.ranking_criteria);setLanguage(p.language);setResolution(p.resolution);setCandidateCount(p.candidate_count);setAllowYoutube(p.allow_youtube);setVoice(p.voice);setEffects(p.effects);setCaptions(p.captions);setOriginalVolume(p.original_volume);setVoiceVolume(p.voice_volume);setEffectsVolume(p.effects_volume);setLayout({...DEFAULT_LAYOUT,...p.layout});setVoiceSettings(p.voice_settings);const next:(Clip|null)[]=p.clips.map(normalize);while(next.length<5)next.push(null);setClips(next);setSelected(0);setPlaying(false);
  }
  function chooseVoice(id:string){const v=VOICES.find(v=>v.id===id);if(v)setVoiceSettings({...voiceSettings,provider:v.provider,voice:v.voice});}
  async function previewMaleVoice(){
    setBusy('Připravuji ukázku mužského hlasu…');setError('');
    try{const r=await api<{url:string}>('/voice-preview',{text:'That recovery turns failure into a win.',language,voice_settings:voiceSettings});voiceAudio.current?.pause();const a=new Audio(r.url);voiceAudio.current=a;await a.play();}catch(e){setError((e as Error).message);}finally{setBusy('');}
  }
  async function uploadReference(file:File){
    if(file.size>40*1024*1024){setError('Předloha může mít nejvýše 40 MB.');return;}
    setBusy('Načítám předlohu a přebírám vzhled…');setError('');
    try{
      const form=new FormData();form.append('file',file);
      const uploaded=await api<Reference>('/templates/upload',form,true);setReference(uploaded);setTemplateFrame(uploaded.frame_time??0);
      const result=await api<Reference>(`/templates/${uploaded.id}/analyze`,{mode:templateMethod,instructions:templateInstructions,base_layout:layout});
      setReference(result);if(result.layout)setLayout({...DEFAULT_LAYOUT,...result.layout});
      setToast(result.analyzed?'Vzhled předlohy použit. Zkontroluj náhled a dolaď detaily.':'Předloha nahraná. Vyber jiný snímek nebo dolaď vzhled ručně.');
    }catch(e){setError((e as Error).message);}finally{setBusy('');if(referenceInput.current)referenceInput.current.value='';}
  }
  async function analyzeReference(){
    if(!reference)return;setBusy('Přebírám polohy, barvy a velikosti z předlohy…');setError('');
    try{
      const r=await api<Reference>(`/templates/${reference.id}/analyze`,{mode:templateMethod,instructions:templateInstructions,frame_time:templateFrame,base_layout:layout});
      setReference(r);if(r.layout)setLayout({...DEFAULT_LAYOUT,...r.layout});
      setToast(r.analyzed?'Vzhled použit. Zkontroluj náhled.':'V tomto snímku není rozpoznaný text. Dolaď vzhled ručně.');
    }catch(e){setError((e as Error).message);}finally{setBusy('');}
  }
  async function saveTemplate(){
    if(!reference)return;setBusy('Ukládám tvůj vzhled…');setError('');
    try{const r=await api<Reference>(`/templates/${reference.id}/settings`,{layout,instructions:templateInstructions});setReference(r);setToast('Vzhled uložen pro asistenta, náhled a export. Projekt ulož tlačítkem Uložit projekt.');}
    catch(e){setError((e as Error).message);}finally{setBusy('');}
  }
  async function sendCommand(command=chatInput){
    if(occupied || !command.trim())return;
    const id=Date.now().toString(36)+Math.random().toString(36).slice(2);assistantTurn.current=id;setChatInput('');setError('');setBusy('Předávám příkaz tvému AI režisérovi…');
    const history=messages.filter(m=>!m.pending).slice(-12).map(({role,content})=>({role,content}));
    setMessages(old=>[...old,{id:id+'u',role:'user',content:command},{id,role:'assistant',content:'Připravuji postup…',pending:true}]);
    try{setJob(await api<Job>('/assistant',{message:command,history,reference_id:reference?.id??null,reference_instructions:reference?templateInstructions:null,state:{topic,title,ranking_criteria:criteria,language,resolution,candidate_count:candidateCount,allow_youtube:allowYoutube,voice,effects,captions,original_volume:originalVolume,voice_volume:voiceVolume,effects_volume:effectsVolume,layout,voice_settings:voiceSettings,clips:clips.filter(Boolean)}}));}
    catch(e){const content=(e as Error).message;setMessages(old=>old.map(m=>m.id===id?{...m,content,pending:false}:m));setError(content);}finally{setBusy('');}
  }

  function updateTime() {
    const el = video.current;
    if (!el || !current) return;
    const before = clips.slice(0, selected).reduce((sum, c) => sum + (c?.duration || 4), 0);
    setElapsed(before + Math.max(0, el.currentTime - current.start));
    if (el.currentTime >= Math.min(current.start + current.duration, current.sourceDuration) - 0.05 && playing) {
      if (selected < 4 && clips[selected + 1]) setSelected(selected + 1);
      else { setPlaying(false); setElapsed(totalDuration); }
    }
  }

  return <div className="app-shell">
    <aside className="rail">
      <button className="brand-mark" title="Nový projekt" aria-label="Nový projekt" onClick={resetProject}><span/><span/><span/></button>
      <nav>
        <button className="rail-button active" title="Editor" aria-label="Editor" onClick={() => setModal(null)}><Clapperboard size={21}/></button>
        <button className="rail-button" title="Uložený projekt" aria-label="Uložit projekt" onClick={saveProject}><FolderOpen size={21}/></button>
        <button className="rail-button" title="Výzkum ranking kanálů" aria-label="Výzkum ranking kanálů" onClick={doResearch} disabled={occupied}><Search size={21}/></button>
        <button className="rail-button" title="Zvukový mix" aria-label="Zvukový mix" onClick={() => setModal('audio')}><AudioLines size={21}/></button>
      </nav>
      <div className="rail-bottom"><button className="rail-button" title="Nastavení" aria-label="Nastavení" onClick={() => setModal('settings')}><Settings2 size={21}/></button><div className="avatar">M</div></div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <a className="wordmark" href="/">rank<span>studio</span><span className="beta">BETA</span></a>
        <div className="breadcrumbs"><span>Workspace</span><span>/</span><strong>Nový Short</strong></div>
        <div className="top-actions"><span className="save-status"><span className={saved ? 'dot green' : 'dot'}/>{saved ? 'Uloženo' : restored ? 'Projekt obnoven' : 'Nový projekt'}</span><button className="button secondary save-button" onClick={saveProject} disabled={occupied}><Save size={15}/> Uložit projekt</button>{health?.owner_login&&<form action="/auth/logout" method="post"><button className="button secondary save-button" disabled={occupied}>Odhlásit se</button></form>}</div>
      </header>
      <main>
        <section className="editor">
          <div className="eyebrow"><span className="tiny-spark"><Sparkles size={12}/></span> OD NÁPADU K TVÉMU DALŠÍMU SHORTU</div>
          <div className="hero-row"><div><h1>Najdi momenty.<br/><span>Vytvoř svůj Short.</span></h1><p>Hledej veřejné klipy podle tématu zdarma.<br className="desktop-break"/> Pět momentů. Tvůj styl. AI hlas volitelně.</p></div><div className="hero-art" aria-hidden="true"><div className="art-orbit"/><div className="art-tile tile-back"><Film size={25}/></div><div className="art-tile tile-front"><Trophy size={33}/><span>#1</span></div><Sparkles className="art-spark" size={23}/></div></div>
          <div className="workflow-tags"><span><Layers3 size={13}/>5 momentů</span><span><Search size={13}/>Hledání zdarma</span><span><Zap size={13}/>Sound effects</span><span className="format-tag">9:16</span></div>

          <TemplatePanel reference={reference} layout={layout} onLayout={setLayout} method={templateMethod} onMethod={setTemplateMethod} aiAvailable={!!health?.ai_scripts} instructions={templateInstructions} onInstructions={setTemplateInstructions} frame={templateFrame} onFrame={setTemplateFrame} input={referenceInput} onUpload={uploadReference} onAnalyze={analyzeReference} onSave={saveTemplate} onRemove={()=>{setReference(null);setTemplateInstructions('');setTemplateFrame(0);}} disabled={occupied}/>
          <details className="paid-assistant"><summary><Sparkles size={13}/>Osobní AI režisér · volitelné placené API<ChevronDown size={13}/></summary>
          <section className="director-card">
            <div className="director-header"><span className="director-avatar"><Sparkles size={17}/></span><div><strong>Tvůj AI režisér</strong><small>Od příkazu po hotový Short</small></div><button className={`director-connection ${health?.ai_scripts?'connected':''}`} onClick={()=>setModal('settings')}><span className="dot"/>{health?.ai_scripts?'API připojeno':'Připojit AI'}</button></div>
            <div className="chat-log" ref={chatLog} aria-live="polite">{messages.length?messages.slice(-12).map(m=><div key={m.id} className={`chat-message ${m.role}`}><span>{m.role==='assistant'?<Sparkles size={12}/>:<span className="user-initial">M</span>}</span><p>{m.content}{m.pending&&<LoaderCircle className="spin" size={12}/>}</p></div>):<div className="director-welcome"><p>Řekni mi, co mám vytvořit. Najdu momenty, vyberu pět nejlepších a dám jim tvůj styl.</p><div className="command-examples"><button disabled={occupied} onClick={()=>setChatInput('Udělej krátký ranking pěti nejlepších fotbalových momentů. Hledej na TikToku a Instagramu, použij hlubší mužský hlas.')}>„Udělej top 5 fotbalových momentů“<ArrowUpRight size={11}/></button><button disabled={occupied} onClick={()=>setChatInput('Použij přiloženou šablonu. Dej číslům stejnou barvu a pozici, titulky podle vzoru.')}>„Použij tuhle šablonu“<ArrowUpRight size={11}/></button></div></div>}</div>
            {reference && <div className="reference-card"><img src={reference.url} alt="Nahraný vzor šablony"/><div><strong>{reference.name}</strong><small>{reference.analyzed?'Styl rozpoznán · přibližná shoda':'Vzor připravený k rozpoznání'}</small></div><button disabled={occupied} onClick={analyzeReference} title="Rozpoznat styl"><WandSparkles size={14}/></button><button disabled={occupied} onClick={()=>setReference(null)} aria-label="Odebrat vzor"><X size={14}/></button></div>}
            <div className="director-composer"><textarea aria-label="Příkaz pro AI režiséra" value={chatInput} maxLength={2500} placeholder="Napiš, co mám udělat…" onChange={e=>setChatInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendCommand();}}} disabled={occupied}/><button className="send-command" aria-label="Odeslat příkaz" onClick={()=>sendCommand()} disabled={occupied||!chatInput.trim()}>{occupied?<LoaderCircle size={17} className="spin"/>:<Send size={17}/>}</button></div>
            <div className="director-bottom"><button disabled={occupied} onClick={()=>referenceInput.current?.click()}><Paperclip size={13}/>Ukaž šablonu</button><span><Mic2 size={11}/>{VOICES.find(v=>v.voice===voiceSettings.voice)?.name} · {language.toUpperCase()}</span><small>Enter odešle · Shift + Enter nový řádek</small></div>
          </section>
          </details>
          <details className="manual-controls" open><summary><Search size={13}/>Automatické hledání klipů<ChevronDown size={13}/></summary><div className="topic-box">
            <label htmlFor="topic"><Sparkles size={16}/> Co dnes rankujeme?</label>
            <div className="search-mode"><label htmlFor="search-mode">REŽIM HLEDÁNÍ</label><div className="select-wrap"><select id="search-mode" value={discoveryMode} disabled={occupied} onChange={e=>setDiscoveryMode(e.target.value as 'free'|'ai')}><option value="free">Zdarma · bez API klíče</option><option value="ai" disabled={!health?.ai_scripts}>AI výběr · placené API{!health?.ai_scripts?' · připoj klíč':''}</option></select><ChevronDown size={12}/></div></div>
            <div className="topic-input-row"><input id="topic" maxLength={100} value={topic} onChange={e => setTopic(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !occupied) discover(); }} placeholder="Například: funny cats, insane football skills…" disabled={occupied}/><button className="button primary" onClick={discover} disabled={occupied}><WandSparkles size={16}/><span>Najít klipy</span><ArrowUpRight size={16}/></button></div>
            <div className="criteria-input"><label htmlFor="criteria">TVŮJ ÚHEL POHLEDU</label><input id="criteria" value={criteria} maxLength={100} onChange={e=>setCriteria(e.target.value)} placeholder="Co porovnáváš? Např. surprise, timing, skill" disabled={occupied}/></div><div className="topic-options"><span className="social-sources"><Clapperboard size={12}/>TikTok + Instagram</span><label className="youtube-option"><input type="checkbox" checked={allowYoutube} onChange={e=>setAllowYoutube(e.target.checked)} disabled={occupied}/>+ YouTube</label><span className="option-divider"/><div className="select-wrap"><select aria-label="Počet kandidátů" value={candidateCount} onChange={e => setCandidateCount(Number(e.target.value))} disabled={occupied}><option value={8}>8 kandidátů</option><option value={12}>12 kandidátů</option><option value={20}>20 kandidátů</option></select><ChevronDown size={12}/></div><span className="topic-ai-note"><span className="dot green"/>{discoveryMode==='free'?'5 scén podle pravidel':'AI vybere 5 nejlepších scén'}</span></div>
            <p className="free-search-note">{discoveryMode==='free'?'Bez placeného API: veřejné hledání, shoda tématu a výběr krátké scény podle pohybu a ostrosti. Obsah a pořadí zkontroluj. AI komentáře ani hlas se nevytvářejí.':'Placené OpenAI API pro hledání, vizuální hodnocení a krátké analytické komentáře.'}</p>
          </div>
          </details>
          {error && <div className="error-banner" role="alert"><Info size={16}/><span>{error}</span><button aria-label="Zavřít chybu" onClick={() => setError('')}><X size={15}/></button></div>}
          {!!job?.search_results?.length && ['done','failed'].includes(job.status) && <details className="found-links"><summary><Search size={13}/>Nalezené zdroje ({job.search_results.length})</summary><p>Veřejné výsledky hledání. Některá videa nemusí jít automaticky stáhnout.</p>{job.search_results.map(result=><a key={result.url} href={result.url} target="_blank" rel="noreferrer">{result.title}<ArrowUpRight size={12}/></a>)}</details>}
          {job && !['done', 'failed'].includes(job.status) && <div className="job-card" role="status"><LoaderCircle size={18} className="spin"/><div><strong>{job.message}</strong><div className="progress-track"><span style={{ width: `${job.progress}%` }}/></div></div><span>{job.progress}%</span></div>}
          {busy && <div className="busy-note" role="status"><LoaderCircle size={14} className="spin"/>{busy}</div>}
          <section className="clips-section">
            <div className="section-heading"><div><h2>Tvoje ranking klipy <span>{ready}<i>/5</i></span></h2><p>Od dobrého k nejlepšímu. Velké finále patří #1.</p></div><button className="text-button" disabled={occupied} onClick={() => chooseFiles(null)}><Upload size={14}/> Nahrát vlastní</button></div>
            <input ref={fileInput} type="file" multiple accept="video/*,.mp4,.mov,.webm,.mkv" className="hidden" onChange={e => e.target.files && upload(e.target.files, uploadTarget.current)}/>
            <div className="clip-list">
              {clips.map((clip, index) => <article key={index} className={`clip-card ${selected === index && clip ? 'selected' : ''} ${index === 4 ? 'winner' : ''}`} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (e.dataTransfer.files.length) upload(e.dataTransfer.files, index); }}>
                <div className="rank-block"><span className="rank-hash">#</span>{5-index}{index === 4 && <Trophy size={11}/>}</div>
                {clip ? <>
                  <button className="clip-thumb" onClick={() => { setSelected(index); setPlaying(false); setElapsed(clips.slice(0,index).reduce((s,c) => s + (c?.duration || 4),0)); }} aria-label={`Zobrazit klip ${5-index}`}><img src={clip.thumbnail} alt={clip.title}/><span><Play size={13} fill="currentColor"/></span><small>{clip.duration.toFixed(1)}s</small></button>
                  <div className="clip-content"><div className="clip-title-row"><input aria-label={`Název klipu ${5-index}`} maxLength={60} value={clip.title} onChange={e => changeClip(index, { title: e.target.value })}/><span className="ready-label"><Check size={10}/>Připraveno</span></div><div className={`voice-input ${words(clip.voiceover)>7 ? 'invalid' : ''}`}><Mic2 size={12}/><input aria-label={`Voiceover klipu ${5-index}`} maxLength={180} value={clip.voiceover} placeholder="Jedna věta. Maximálně 7 slov." onChange={e => changeClip(index,{voiceover:e.target.value})}/><button title="Poslechnout AI hlas" aria-label={`Poslechnout voiceover ${5-index}`} disabled={occupied || !clip.voiceover} onClick={() => playVoice(clip)}><Play size={12}/></button><span>{words(clip.voiceover)}<i>/7</i></span></div><div className="clip-meta"><label>Začátek <input type="number" min={0} max={Math.max(0,clip.sourceDuration-0.3)} step={0.1} value={Number(clip.start.toFixed(1))} aria-label={`Začátek klipu ${5-index}`} onChange={e => changeClip(index,{start:Math.max(0, Math.min(clip.sourceDuration-0.3,Number(e.target.value)))})}/>s</label><span>·</span><label>Délka <input type="number" min={2} max={8} step={0.5} value={clip.duration} aria-label={`Délka klipu ${5-index}`} onChange={e => changeClip(index,{duration:Math.max(2,Math.min(8,Number(e.target.value)))})}/>s</label>{clip.reason && <span title={clip.reason} className="ai-selected"><Sparkles size={10}/>AI výběr</span>}{clip.source_url && <a href={clip.source_url} target="_blank" rel="noreferrer" title="Původní zdroj">Zdroj <ArrowUpRight size={9}/></a>}</div></div>
                  <div className="clip-actions"><button aria-label={`Posunout klip ${5-index} nahoru`} disabled={index===0 || occupied} onClick={() => moveClip(index,-1)}><ArrowUp size={13}/></button><button aria-label={`Posunout klip ${5-index} dolů`} disabled={index===4 || occupied} onClick={() => moveClip(index,1)}><ArrowDown size={13}/></button><button aria-label={`Nahradit klip ${5-index}`} disabled={occupied} onClick={() => chooseFiles(index)}><RotateCcw size={12}/></button><button aria-label={`Odstranit klip ${5-index}`} disabled={occupied} onClick={() => {setClips(old=>old.map((c,i)=>i===index?null:c)); if(selected===index)setPlaying(false);}}><X size={12}/></button></div>
                </> : <button className="empty-clip" disabled={occupied} onClick={() => chooseFiles(index)}><span className="empty-thumb">{uploadIndex===index?<LoaderCircle size={19} className="spin"/>:<Plus size={21}/>}</span><span><strong>{index===4?'Vítězný moment':'Místo pro tvůj moment'}</strong><small>Přetáhni video nebo klikni pro nahrání</small></span><span className="empty-length">2–8 s</span></button>}
              </article>)}
            </div>
            <div className="clip-footer"><span><ShieldCheck size={13}/>Jedna scéna. Žádné zbytečné čekání.</span><button className="text-button" disabled={occupied || ready!==5} onClick={generateScripts}><Sparkles size={13}/> Vygenerovat komentáře</button></div>
            <button className="demo-button" disabled={occupied} onClick={loadDemo}><Play size={12}/> Jen si to prohlížíš? <span>Vyzkoušet syntetickou ukázku</span><ArrowUpRight size={13}/></button>
          </section>
        </section>
        <aside className="preview-panel">
          <div className="preview-heading"><h2><span className="dot green"/>Náhled Shortu</h2><span className="preview-badge">9:16</span></div>
          <div className="phone" onClick={() => {if(current)setPlaying(!playing);}}>
            {current ? <video ref={video} key={current.url} src={current.url} poster={current.thumbnail} muted={muted} playsInline onLoadedMetadata={() => { if(video.current)video.current.currentTime=current.start; }} onTimeUpdate={updateTime} onEnded={() => {if(playing && selected<4 && clips[selected+1])setSelected(selected+1);else setPlaying(false);}} onError={() => setError('Náhled klipu není dostupný. Nahrajte jej znovu.')} /> : <div className="phone-art"><div className="art-grid"/><div className="orb orb-one"/><div className="orb orb-two"/><div className="phone-art-label"><Film size={21}/><span>Tvoje momenty.<br/>Tvoje pořadí.</span></div></div>}
            <div className="phone-overlay" style={{fontFamily:layout.font==='serif'?'RankSerif,Georgia,serif':layout.font==='condensed'?'RankCondensed,Arial,sans-serif':'RankBold,Arial,sans-serif',background:`linear-gradient(180deg,rgba(0,0,0,${layout.header_darkness}) 0%,transparent 29%,transparent 68%,rgba(0,0,0,.65))`}}><span className="phone-series">THE TOP FIVE</span><h3 style={{top:`${layout.title_y*100}%`,fontSize:`${layout.title_size*100}cqw`,color:`#${layout.title_color}`,textAlign:layout.title_align??'center',left:`${layout.title_align==='left'?layout.title_x*100:5}%`,right:`${layout.title_align==='right'?layout.title_x*100:5}%`}}>{title || 'TOP 5 MOMENTS'}</h3><div className="phone-rank" style={{top:`${layout.rank_y*100}%`,left:`${layout.rank_x*100}%`,fontSize:`${layout.rank_size*100}cqw`,color:`#${layout.rank_color}`}}>#{5-selected}</div>{current && layout.show_label && <div className="phone-clip-label" style={{color:`#${layout.rank_color}`}}>{current.title}</div>}{captions && current?.voiceover && <p className="phone-caption" style={{top:`${layout.caption_y*100}%`,fontSize:`${layout.caption_size*100}cqw`,color:`#${layout.caption_color}`,textAlign:layout.caption_align??'center',left:`${layout.caption_align==='left'?layout.caption_x*100:7}%`,right:`${layout.caption_align==='right'?layout.caption_x*100:7}%`}}>{current.voiceover}</p>}{layout.show_criteria && <div className="phone-criteria">{criteria}</div>}<div className="phone-bottom"><span className="phone-watermark">RANK STUDIO</span><div className="phone-dots">{clips.map((_,i)=><span key={i} className={i===selected?'active':''}/>)}</div></div></div>
            {current && !playing && <button className="phone-play" aria-label="Přehrát náhled" onClick={e => {e.stopPropagation();setPlaying(true);}}><Play size={23} fill="currentColor"/></button>}
          </div>
          <div className="playback"><button aria-label={playing?'Pozastavit':'Přehrát'} disabled={!current} onClick={() => setPlaying(!playing)}>{playing?<Pause size={16}/>:<Play size={16} fill="currentColor"/>}</button><span>{time(elapsed)}</span><div className="playback-track"><span style={{width:`${Math.min(100, elapsed/totalDuration*100)}%`}}/></div><span>{time(totalDuration)}</span><button aria-label={muted?'Zapnout zvuk':'Ztlumit'} onClick={() => setMuted(!muted)}>{muted?<VolumeX size={16}/>:<Volume2 size={16}/>}</button></div>
          <div className="timeline">{clips.map((c,i)=><button key={i} className={selected===i?'selected':''} onClick={()=>{setSelected(i);setPlaying(false);setElapsed(clips.slice(0,i).reduce((s,c)=>s+(c?.duration||4),0));}} aria-label={`Náhled pozice ${5-i}`} style={c?{backgroundImage:`linear-gradient(0deg, rgba(0,0,0,.6), rgba(0,0,0,.1)),url(${c.thumbnail})`}:undefined}><span>#{5-i}</span><small>{c?.duration??4}s</small></button>)}</div>
          <p className="preview-note">Náhled klipů · AI hlas a efekty uslyšíš v exportu.</p>
          <div className="output-settings"><div className="output-heading"><h2>Finální doladění</h2><button title="Zvukový mix" aria-label="Zvukový mix" onClick={()=>setModal('audio')}><SlidersHorizontal size={15}/></button></div><label className="video-title-label" htmlFor="video-title">NÁZEV VE VIDEU</label><input id="video-title" className="video-title-input" maxLength={70} value={title} onChange={e=>setTitle(e.target.value)}/><label className="video-title-label voice-label" htmlFor="male-voice">MUŽSKÝ HLAS</label><div className="voice-choice-row"><div className="select-wrap"><select id="male-voice" value={`${voiceSettings.provider}:${voiceSettings.voice}`} onChange={e=>chooseVoice(e.target.value)}>{VOICES.map(v=><option key={v.id} value={v.id}>{v.name}</option>)}</select><ChevronDown size={12}/></div><button className="voice-sample" title="Poslechnout mužský hlas" aria-label="Poslechnout mužský hlas" disabled={occupied} onClick={previewMaleVoice}><Play size={13}/></button></div><div className="setting-row"><span><Mic2 size={15}/>AI voiceover <small>{language==='en'?'English':'Čeština'}</small></span><Toggle value={voice} set={setVoice} label="AI voiceover"/></div><div className="setting-row"><span><Zap size={15}/>Zvukové efekty</span><Toggle value={effects} set={setEffects} label="Zvukové efekty"/></div><div className="setting-row"><span><Clapperboard size={15}/>Titulky ve videu</span><Toggle value={captions} set={setCaptions} label="Titulky ve videu"/></div><div className="format-settings"><div><label htmlFor="resolution">ROZLIŠENÍ</label><div className="select-wrap"><select id="resolution" value={resolution} onChange={e=>setResolution(e.target.value)}><option value="1080">1080 × 1920</option><option value="720">720 × 1280</option></select><ChevronDown size={12}/></div></div><div><label htmlFor="language">JAZYK HLASU</label><div className="select-wrap"><select id="language" value={language} onChange={e=>setLanguage(e.target.value)}><option value="en">English</option><option value="cs">Čeština</option></select><ChevronDown size={12}/></div></div></div></div>
          <div className="export-card"><div><span><Film size={13}/>MP4 · H.264</span><span>{time(totalDuration)} · {resolution}p</span></div>{exported?<a className="button primary export-button" href={exported} download><Download size={17}/>Stáhnout Short<Check size={17}/></a>:<button className="button primary export-button" onClick={exportVideo} disabled={occupied}>{occupied?<LoaderCircle className="spin" size={17}/>:<Download size={17}/>}Exportovat Short<ArrowUpRight size={17}/></button>}<p>Připraveno pro YouTube Shorts, Reels i TikTok.</p></div>
          <button className="research-link" disabled={occupied} onClick={doResearch}><Search size={14}/><span>Co funguje u ranking kanálů?</span><ArrowUpRight size={14}/></button>
        </aside>
      </main>
      <footer className="app-footer"><span>Malé momenty. Velký replay.</span><span>RANK STUDIO <i>✦</i> MADE FOR SHORTS</span></footer>
    </div>
    {toast && <div className="toast" role="status"><Check size={16}/>{toast}<button onClick={()=>setToast('')} aria-label="Zavřít oznámení"><X size={14}/></button></div>}
    {modal && <div className="modal-backdrop" onClick={()=>setModal(null)}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onClick={e=>e.stopPropagation()}><div className="modal-head"><span className="modal-icon">{modal==='settings'?<Settings2 size={20}/>:modal==='audio'?<AudioLines size={20}/>:<Search size={20}/>}</span><button aria-label="Zavřít dialog" onClick={()=>setModal(null)}><X size={20}/></button></div><h2 id="modal-title">{modal==='settings'?'Připoj svůj tvůrčí workflow':modal==='audio'?'Ať každý moment zazní':'Co funguje na YouTube'}</h2>
      {modal==='settings' && <><p className="modal-intro">Hledání v režimu Zdarma nepotřebuje klíč. Klíče přidej pouze pro volitelné placené AI funkce, bezpečně do nastavení serveru.</p><Integration name="Vizuální AI výběr a komentáře · placené API" code="OPENAI_API_KEY" ready={!!health?.ai_scripts} text="Hledání TikToku a Instagramu, hodnocení skutečných scén a komentáře do 7 slov."/><Integration name="Kvalitní mužský hlas Onyx / Echo" code="OPENAI_API_KEY" ready={!!health?.ai_scripts} text="Výchozí hlasový model gpt-4o-mini-tts. Přirozené frázování, volitelný tón a ukázka před exportem."/><Integration name="Lokální anglický AI hlas" code="python scripts/download_models.py --language en" ready={!!health?.voices.en} text="Piper / Lessac. Běží lokálně bez placeného klíče. Není ověřen jako hlas z reference."/><Integration name="Hlas podle tvého výběru" code="ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID" ready={!!(health?.elevenlabs&&health?.reference_voice)} text="Volitelný ElevenLabs hlas. Přesný hlas z ukázky je nutné nejdřív identifikovat."/><div className="modal-note"><Info size={15}/><span>TikTok i Instagram mohou blokovat automatické stažení. Aplikace takové klipy přeskočí a nikdy je nenahradí vymyšleným výsledkem. Přesný styl reference zatím není ověřen.</span></div><button className="button primary" onClick={async()=>{try {setHealth(await api<Health>('/health'));setToast('Stav integrací aktualizován.');}catch(e){setError((e as Error).message);}}}><RotateCcw size={15}/>Znovu ověřit připojení</button></>}
      {modal==='audio' && <><p className="modal-intro">Voiceover vede. Původní zvuk nech tiše pod ním, efekt zvýrazní začátek každého klipu.</p><label className="delivery-label">PROJEV HLASU<textarea value={voiceSettings.delivery} maxLength={300} onChange={e=>setVoiceSettings({...voiceSettings,delivery:e.target.value})}/></label><label className="volume-slider"><span>Tempo hlasu<strong>{voiceSettings.speed.toFixed(2)}×</strong></span><input type="range" min={.85} max={1.2} step={.05} value={voiceSettings.speed} onChange={e=>setVoiceSettings({...voiceSettings,speed:Number(e.target.value)})}/></label><VolumeSlider label="AI voiceover" value={voiceVolume} set={setVoiceVolume} max={1.5}/><VolumeSlider label="Původní zvuk klipu" value={originalVolume} set={setOriginalVolume}/><VolumeSlider label="Zvukové efekty" value={effectsVolume} set={setEffectsVolume}/><div className="modal-note"><Zap size={16}/><span>Krátký whoosh pro #5 až #2. Vítězný zvuk pro #1. Hlas se automaticky vejde do délky klipu.</span></div><button className="button primary" onClick={()=>setModal(null)}>Hotovo<Check size={15}/></button></>}
      {modal==='research' && <><p className="modal-intro">AI průzkum veřejných výsledků YouTube pro Aura Shorts a další ranking kanály. U každého zjištění zůstává odkaz na zdroj.</p>{busy?<div className="research-loading"><LoaderCircle className="spin" size={25}/><span>{busy}</span></div>:research?<><div className="research-results">{research.channels.map((c,i)=><a key={i} href={c.url} target="_blank" rel="noreferrer"><strong>{c.name}<ArrowUpRight size={14}/></strong><p>{c.observation}</p><small>{c.evidence}</small></a>)}</div><ul className="research-tips">{research.recommendations.map((r,i)=><li key={i}>{r}</li>)}</ul><div className="modal-note"><Info size={16}/><span>{research.limitations || 'Výsledky vycházejí z dostupných veřejných podkladů. Přesný hlas je nutné ověřit z videa.'}</span></div></>:<div className="modal-note"><Info size={16}/><span>{error || 'Výzkum vyžaduje připojené AI API. Klíč zadej bezpečně v nastavení prostředí.'}</span></div>}<button className="button secondary" disabled={occupied} onClick={doResearch}><Search size={15}/>Zopakovat výzkum</button></>}
    </section></div>}
  </div>;
}

function Toggle({ value, set, label }: { value: boolean; set: (v:boolean)=>void; label:string }) { return <button className={`toggle ${value?'on':''}`} onClick={()=>set(!value)} role="switch" aria-checked={value} aria-label={label}><span/></button>; }
function Integration({name,code,ready,text}:{name:string;code:string;ready:boolean;text:string}) { return <div className="integration"><div><strong>{name}</strong><span className={ready?'connected':'not-connected'}>{ready?<Check size={12}/>:<span className="dot"/>}{ready?'Připojeno':'Vyžaduje nastavení'}</span></div><p>{text}</p><code>{code}</code></div>; }
function VolumeSlider({label,value,set,max=1}:{label:string;value:number;set:(v:number)=>void;max?:number}) { return <label className="volume-slider"><span>{label}<strong>{Math.round(value*100)}%</strong></span><input type="range" min={0} max={max} step={0.01} value={value} onChange={e=>set(Number(e.target.value))}/></label>; }

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
