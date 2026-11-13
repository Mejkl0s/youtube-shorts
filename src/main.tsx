import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowDown, ArrowUp, ArrowUpRight, AudioLines, Check, ChevronDown, Clapperboard, Download, Film, FolderOpen, Info, Layers3, LoaderCircle, Mic2, MessageSquare, Paperclip, Send, Pause, Play, Plus, RotateCcw, Save, Search, Settings2, ShieldCheck, SlidersHorizontal, Sparkles, Trophy, Upload, Volume2, VolumeX, WandSparkles, X, Zap } from 'lucide-react';
import '../desktop/theme.css';
import './styles.css';
import './fonts.css';
import TemplatePanel from './TemplatePanel';
import {DesktopAIProvider,DesktopTopbar,DesktopWritingPanel,DesktopAISetup,useDesktopAI} from './DesktopAI';
import {bootstrapDesktop,collectState,desktopAPI,flushDesktop,restoringState} from './desktop';
import ProjectExchange from './ProjectExchange';
import SourceSessions from './SourceSessions';
import RankingNumbers from './RankingNumbers';
import RankSettings from './RankSettings';
import ClipEffects,{EFFECT_NAMES,type EffectSettings,type EffectKind} from './ClipEffects';
import TitleSettings from './TitleSettings';
import TitleOverlay from './TitleOverlay';
import ClipCleanup,{BlurMasks,safeBlurRegions,type BlurRegion} from './ClipCleanup';
import ClipTrimmer,{type Framing} from './ClipTrimmer';
import './studio.css';
import {DEFAULT_LAYOUT,fontFamily,type Layout,type Reference} from './template';

const MAX_PROJECT_SECONDS=40;
type VisualEvidence={time:number;observation:string};
type Clip = { visual_review?:{provider?:string;model?:string|null;method:string;confidence:number;score:number;setup:VisualEvidence;action:VisualEvidence;outcome:VisualEvidence}|null; selection_version?:'whole-scene-v1'|'manual-v1'|'visual-event-v2'|null; framing?:Framing; has_audio?:boolean; source_asset_id?:string; source_start?:number; scene_start?:number; scene_end?:number; review_required?:boolean; rank_note?:string; rank_note_auto?:boolean; end_audio?:'auto'|'keep'|'mute'; effects_mode?:'auto'|'manual'|'custom'|'off'; effect_at?:number; effect_cues?:{kind:EffectKind;at:number;gain:number}[]; blur_regions?:BlurRegion[]; id: string; name: string; title: string; voiceover: string; narration_mode?:'rank'|'custom'; duration: number; sourceDuration: number; start: number; url: string; thumbnail: string; reason?: string; source_url?: string };
type VoiceSettings = { provider: 'openai'|'elevenlabs'|'piper'|'edge'; voice: string; speed: number; delivery: string };
type ChatMessage = { id: string; role: 'user'|'assistant'; content: string; pending?: boolean };
const DEFAULT_VOICE: VoiceSettings = { provider:'edge', voice:'free_male', speed:.95, delivery:'A confident, natural male narrator. Clear English, conversational energy, varied emphasis. No exaggerated shouting. Let the key observation land.' };
const VOICES = [{id:'edge:free_male',name:'Andrew / Antonín · zdarma bez klíče',provider:'edge',voice:'free_male'}, {id:'openai:onyx',name:'Onyx · placené OpenAI API',provider:'openai',voice:'onyx'}, {id:'openai:echo',name:'Echo · placené OpenAI API',provider:'openai',voice:'echo'}, {id:'elevenlabs:adam',name:'Adam · placené ElevenLabs API',provider:'elevenlabs',voice:'adam'}, {id:'elevenlabs:josh',name:'Josh · placené ElevenLabs API',provider:'elevenlabs',voice:'josh'}, {id:'elevenlabs:antoni',name:'Antoni · placené ElevenLabs API',provider:'elevenlabs',voice:'antoni'}, {id:'elevenlabs:custom',name:'Vlastní · placené ElevenLabs API',provider:'elevenlabs',voice:'custom'}, {id:'piper:local',name:'Piper · lokální alternativa',provider:'piper',voice:'local'}] as const;
type AIProject = { avoid_repeats?:boolean; topic:string; title:string; ranking_criteria:string; language:string; resolution:string; candidate_count:number; allow_youtube:boolean; voice:boolean; effects:boolean; captions:boolean; original_volume:number; voice_volume:number; effects_volume:number; layout:Layout; voice_settings:VoiceSettings; clips:Record<string,unknown>[] };
type LocalVision={supported:boolean;ready:boolean;model:string;message:string;setup_running?:boolean;memory?:{gpu_bytes:number;total_bytes:number}};
type Health = { desktop?:boolean; local_vision?:LocalVision; voices: Record<string, boolean>; ai_scripts: boolean; elevenlabs: boolean; reference_voice: boolean; owner_login?:boolean;free_voice?:boolean;local_mode?:boolean };
type Job = { effects_plan?:{rank:number;asset_id:string;clip_start:number;clip_duration:number;source:string;reason:string;events:{kind:EffectKind;at:number;gain:number;observation?:string}[]}[]; ai?:{provider:string;model:string}; id: string; status: string; progress: number; message: string; download?: string; cancel_requested?:boolean; elapsed_seconds?:number; remaining_seconds?:number; limit_seconds?:number; downloaded_sources?:Record<string,unknown>[]; clips?: Record<string, unknown>[]; partial_clips?: Record<string, unknown>[]; candidate_count?: number; kind?: string; max_duration?:number; mode?: 'free'|'local'|'ai'; search_results?: {url:string;title:string}[]; warnings?:string[]; youtube_fallback?:boolean; source_stats?:Record<string,{found:number;downloaded:number;failed:number;reviewed?:number;accepted?:number}>; download_failures?:{source:string;url:string;kind:string;reason:string}[]; assistant_reply?: string; project?: AIProject; reference?: Reference; research?: Research };
type Research = { channels: { name: string; url: string; observation: string; evidence: string }[]; recommendations: string[]; limitations: string };
const words = (text: string) => text.match(/[\p{L}\p{N}]+(?:['’\-][\p{L}\p{N}]+)*/gu)?.length ?? 0;
const rankLine=(index:number,lang:string)=> (lang==='cs'?['Páté místo.','Čtvrté místo.','Třetí místo.','Druhé místo.','První místo.']:['Number five.','Number four.','Number three.','Number two.','Number one.'])[index];
const blankClips = (): (Clip | null)[] => Array(5).fill(null);
const time = (n: number) => `${Math.floor(n / 60).toString().padStart(2, '0')}:${Math.floor(n % 60).toString().padStart(2, '0')}`;
const normalize = (a: Record<string, unknown>,_index=0): Clip => ({ ...(a as unknown as Clip), framing:a.framing==='fit'?'fit':'fill',rank_note:String(a.rank_note??''), title: String(a.title ?? a.name), voiceover: String(a.voiceover ?? ''), start: Number(a.start ?? 0), sourceDuration: Number(a.sourceDuration ?? a.duration), duration: a.start !== undefined ? Number(a.duration) : Math.min(30, Number(a.duration)) });

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
  useEffect(()=>{
    const bar=document.querySelector('.topbar');
    if(!bar)return;
    const measure=()=>document.documentElement.style.setProperty('--studio-topbar-height',`${bar.getBoundingClientRect().height}px`);
    const observer=new ResizeObserver(measure);observer.observe(bar);measure();
    return()=>observer.disconnect();
  },[]);
  const desktopAI=useDesktopAI();
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
  const [titleFollowsTopic,setTitleFollowsTopic]=useState(true);
  const [criteria, setCriteria] = useState('Surprise, timing and skill');
  const [allowYoutube, setAllowYoutube] = useState(true);
  const [language, setLanguage] = useState('en');
  const [resolution, setResolution] = useState('1080');
  const [voice, setVoice] = useState(true);
  const [effects, setEffects] = useState(true);
  const [captions, setCaptions] = useState(true);
  const [originalVolume, setOriginalVolume] = useState(0.8);
  const [voiceVolume, setVoiceVolume] = useState(1);
  const [effectsVolume, setEffectsVolume] = useState(0.55);
  const [candidateCount, setCandidateCount] = useState(window.rankDesktop?100:24);
  const [searchDepth,setSearchDepth]=useState<'quick'|'thorough'>(window.rankDesktop?'thorough':'quick');
  const [maxDuration,setMaxDuration]=useState(window.rankDesktop?25:40);
  const [durationDraft,setDurationDraft]=useState<string|null>(null);
  const [autoPreview,setAutoPreview]=useState(true);
  const [avoidRepeats,setAvoidRepeats]=useState(true);
  const sourceHistory=useRef<string[]>([]);
  const assetHistory=useRef<string[]>([]);
  const [previousClips,setPreviousClips]=useState<(Clip|null)[]|null>(null);
  const pendingSearchPreview=useRef<((clips:Clip[])=>Promise<Job>)|null>(null);
  const [blurText,setBlurText]=useState(true);
  const [trim,setTrim]=useState<{index:number;context:{full_source?:boolean;source:{url:string;duration?:number};bounds:{start:number;end:number};current:{start:number;end:number};message:string}}|null>(null);
  const [cleanupIndex,setCleanupIndex]=useState<number|null>(null);
  const compilationInput=useRef<HTMLInputElement>(null);
  const [discoveryMode, setDiscoveryMode] = useState<'free'|'local'>(window.rankDesktop?'local':'free');
  const [localSetup,setLocalSetup]=useState(false);
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [noteTime,setNoteTime]=useState(1);
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
  const legacyFourSecondCuts=restored&&ready===5&&clips.every(c=>c&&Math.abs(c.duration-4)<.01&&!c.selection_version);
  const totalDuration = clips.reduce((sum, c) => sum + (c?.duration ?? 4), 0);
  const overDuration=clips.filter(Boolean).reduce((sum,c)=>sum+(c?.duration??0),0)>maxDuration+.000001;
  const hasVoice = voiceSettings.provider==='edge' ? !!health?.free_voice : voiceSettings.provider==='openai' ? !!health?.ai_scripts : voiceSettings.provider==='elevenlabs' ? !!health?.elevenlabs : !!health?.voices[language];
  const occupied = !!busy || desktopAI.busy || !!(job && !['done', 'failed'].includes(job.status));

  useEffect(() => {
    api<Health>('/health').then(h=>{setHealth(h);if(!h.ai_scripts)setTemplateMethod('free');}).catch(() => setError('Server není dostupný. Spusťte backend podle README.'));
    try {
      const savedProject = JSON.parse(localStorage.getItem('rank-studio-project') ?? 'null');
      if (savedProject?.clips?.length === 5) {
        setClips(savedProject.clips.map((c:Record<string,unknown>|null,i:number)=>c?normalize(c,i):null)); setTitle(savedProject.title || 'TOP 5 MOMENTS'); setTopic(savedProject.topic || '');setTitleFollowsTopic(savedProject.titleFollowsTopic??true); setCriteria(savedProject.criteria || 'Surprise, timing and skill'); setLanguage(savedProject.language || 'en');
        setVoice(savedProject.voice ?? true);setAutoPreview(savedProject.autoPreview??true);setAvoidRepeats(savedProject.avoidRepeats??true); setEffects(savedProject.effects ?? true); setCaptions(savedProject.captions ?? true); setResolution(savedProject.resolution || '1080'); setDiscoveryMode(savedProject.discoveryMode==='local'||window.rankDesktop&&savedProject.searchDepth!=='quick'?'local':'free');setSearchDepth(savedProject.searchDepth==='thorough'?'thorough':savedProject.searchDepth==='quick'?'quick':window.rankDesktop?'thorough':'quick');setMaxDuration(savedProject.maxDuration??40);
        setBlurText(savedProject.blurText??true);setAllowYoutube(savedProject.allowYoutube ?? true); setCandidateCount(window.rankDesktop&&!savedProject.searchDepth?100:savedProject.candidateCount===12?24:savedProject.candidateCount||24); setOriginalVolume(savedProject.originalVolume===.12||savedProject.originalVolume===.15?.8:savedProject.originalVolume??.8); setVoiceVolume(savedProject.voiceVolume ?? 1); setEffectsVolume(savedProject.effectsVolume ?? 0.55);
        setLayout({...DEFAULT_LAYOUT,...savedProject.layout}); setVoiceSettings(['edge','piper'].includes(savedProject.voiceSettings?.provider)?savedProject.voiceSettings:DEFAULT_VOICE); setReference(savedProject.reference || null);setTemplateInstructions(savedProject.templateInstructions??savedProject.reference?.instructions??'');setTemplateFrame(savedProject.reference?.frame_time??0);setTemplateMethod('free'); setRestored(true); setToast('Uložený projekt byl obnoven.');
      }
    } catch { localStorage.removeItem('rank-studio-project'); }
    try{const history=JSON.parse(localStorage.getItem('rank-studio-assets')||'[]');if(Array.isArray(history))assetHistory.current=history.filter((id:unknown)=>typeof id==='string'&&/^[a-f0-9]{32}$/.test(id)).slice(-180);const backup=JSON.parse(localStorage.getItem('rank-studio-previous-clips')||'null');if(Array.isArray(backup)&&backup.length===5)setPreviousClips(backup.map((c,i)=>c?normalize(c,i):null));}catch{}
    try{const history=JSON.parse(localStorage.getItem('rank-studio-sources')||'[]');if(Array.isArray(history))sourceHistory.current=history.filter((url:unknown)=>typeof url==='string'&&/^https:\/\/(www\.)?(tiktok\.com|instagram\.com|youtube\.com|youtu\.be)\//.test(url)&&url.length<=500).slice(-180);}catch{}
    try { const history=JSON.parse(localStorage.getItem('rank-studio-chat') || '[]'); if(Array.isArray(history))setMessages(history.slice(-30).filter(m=>['user','assistant'].includes(m.role)).map(m=>m.pending?{...m,pending:false,content:'Po obnovení nebyl výsledek tohoto příkazu ověřen. Zkontroluj projekt.'}:m)); } catch {}
    return () => { voiceAudio.current?.pause(); };
  }, []);
  const desktopProjectSnapshot=JSON.stringify({ clips, title, topic, titleFollowsTopic, criteria, allowYoutube, layout, voiceSettings, reference, language, voice, effects, captions, resolution, originalVolume, voiceVolume, effectsVolume, candidateCount, discoveryMode, searchDepth, maxDuration, blurText, autoPreview, avoidRepeats, templateMethod, templateInstructions });
  const desktopProjectRef=useRef(desktopProjectSnapshot);desktopProjectRef.current=desktopProjectSnapshot;
  useEffect(()=>{if(!window.rankDesktop)return;const saveCurrent=()=>{if(!restoringState())localStorage.setItem('rank-studio-project',desktopProjectRef.current);};window.addEventListener('rank-desktop-save-current',saveCurrent);return()=>window.removeEventListener('rank-desktop-save-current',saveCurrent);},[]);
  useEffect(()=>{if(!window.rankDesktop)return;const timer=setTimeout(()=>{if(restoringState())return;try{localStorage.setItem('rank-studio-project',desktopProjectSnapshot);}catch{setError('Rozpracovaný projekt se nepodařilo uložit.');}},600);return()=>clearTimeout(timer);},[desktopProjectSnapshot]);
  useEffect(()=>{if(!window.rankDesktop)return;const refresh=(event:Event)=>{const detail=(event as CustomEvent).detail;if(detail?.search==='technical'){setDiscoveryMode('free');setSearchDepth('quick');setCandidateCount(24);}else if(detail?.search==='ai'){setDiscoveryMode('local');setSearchDepth('thorough');setCandidateCount(100);}else if(detail?.selectAI)setDiscoveryMode('local');api<Health>('/health').then(setHealth).catch(()=>setError('Místní backend neodpovídá.'));};const failed=()=>setError('Průběžné uložení selhalo. Projekt můžeš exportovat nebo zkusit uložit znovu.');window.addEventListener('rank-desktop-ai-changed',refresh);window.addEventListener('rank-desktop-storage-error',failed);return()=>{window.removeEventListener('rank-desktop-ai-changed',refresh);window.removeEventListener('rank-desktop-storage-error',failed);};},[]);
  useEffect(() => { setSaved(false); setExported(pendingDownload.current); pendingDownload.current=null; }, [clips, title, titleFollowsTopic, criteria, language, voice, effects, captions, resolution, originalVolume, voiceVolume, effectsVolume, layout, voiceSettings]);
  useEffect(()=>{try{localStorage.setItem('rank-studio-chat',JSON.stringify(messages.slice(-30)));}catch{} if(chatLog.current)chatLog.current.scrollTop=chatLog.current.scrollHeight;},[messages]);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(''), 5000); return () => clearTimeout(t); }, [toast]);
  useEffect(() => {
    if (!job || ['done', 'failed'].includes(job.status)) return;
    let inFlight=false;
    const interval = setInterval(async () => {
      if(inFlight)return;inFlight=true;
      try {
        const next = await api<Job>(`/jobs/${job.id}`);
        setJob(next);if(next.max_duration!==undefined)setMaxDuration(next.max_duration);
        if(next.kind==='assistant' && next.assistant_reply && assistantTurn.current){setMessages(old=>old.map(m=>m.id===assistantTurn.current?{...m,content:next.assistant_reply!,pending:!['done','failed'].includes(next.status)}:m));}
        if(next.kind==='assistant' && ['done','failed'].includes(next.status)){if(next.project){pendingDownload.current=next.download || null;applyProject(next.project);}else if(next.download)setExported(next.download);if(next.reference){setReference(next.reference);setTemplateInstructions(next.reference.instructions??'');setTemplateFrame(next.reference.frame_time??0);}if(next.research){setResearch(next.research);setModal('research');}}
        if (next.status === 'failed') {
          pendingSearchPreview.current=null;
          setError(next.message+(next.kind==='discover'&&!next.partial_clips?.length&&previousClips?.some(Boolean)?' Nové hledání nepřidalo žádné klipy. Předchozí klipy jsou uložené zvlášť; tlačítkem Vrátit předchozí klipy je můžeš obnovit.':''));
          if (next.kind==='discover' && next.partial_clips?.length) {
            const recovered:(Clip|null)[]=next.partial_clips.slice(0,5).map(normalize);
            while(recovered.length<5)recovered.push(null);
            rememberSources(recovered);setClips(recovered);setSelected(0);setPlaying(false);
            setToast(`Zachováno ${next.partial_clips.length}/5 klipů. Zbývající nahraj do prázdných míst.`);
          }
        }
        if (next.status === 'done') {
          if (next.kind==='rank-notes' && next.clips) {
            const notes=new Map(next.clips.map(c=>[c.id,c]));
            setClips(old=>old.map(c=>{const result=c&&notes.get(c.id);return c&&result&&Number(result.start)===c.start&&Number(result.duration)===c.duration?{...c,rank_note:String(result.rank_note??''),rank_note_auto:true}:c;}));setToast(next.message);
          } else if (next.clips) {
            const fresh=next.clips.map(normalize).map((c,i)=>next.kind==='discover'&&voice&&!c.voiceover.trim()?{...c,voiceover:rankLine(i,language),narration_mode:'rank' as const}:c);
            rememberSources(fresh);setClips(fresh);setSelected(0);setPlaying(false);
            setToast(['recut','rank-notes'].includes(next.kind??'')?next.message:'Klipy jsou připravené. Zkontroluj obsah, pointu a pořadí.');
            if(['discover','visual-review','cleanup'].includes(next.kind??'')&&pendingSearchPreview.current){
              const createPreview=pendingSearchPreview.current;pendingSearchPreview.current=null;
              setBusy('Připravuji hotový náhled s vybraným zvukem…');
              try{setJob(await createPreview(fresh));}catch(e){setError(`Klipy jsou připravené, ale zvukový náhled se nepodařilo vytvořit: ${(e as Error).message}`);}finally{setBusy('');}
            }
          }
          if (next.download && next.kind!=='assistant') { if(next.clips)pendingDownload.current=next.download;setExported(next.download); setToast('Export dokončen. Váš Short je připravený!'); }
        }
      } catch (e) { pendingSearchPreview.current=null;setError((e as Error).message); setJob(null); }finally{inFlight=false;}
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
  useEffect(()=>{
    if(!playing||!current){setNoteTime(1);return;}
    setNoteTime(0);let frame=0;
    const tick=()=>{const t=Math.max(0,(video.current?.currentTime??current.start)-current.start);setNoteTime(t);if(t<.5)frame=requestAnimationFrame(tick);};
    frame=requestAnimationFrame(tick);return()=>cancelAnimationFrame(frame);
  },[playing,selected,current?.url]);
  useEffect(() => { if(video.current) video.current.volume = Math.min(1,originalVolume); }, [originalVolume, current?.url]);
  useEffect(() => { if (playing && current) video.current?.play().catch(() => setPlaying(false)); else video.current?.pause(); }, [playing]);
  useEffect(() => {
    if (!modal) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setModal(null); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [modal]);

  function rememberSources(items:(Clip|null)[]){
    sourceHistory.current=[...new Set([...sourceHistory.current,...items.flatMap(c=>c?.source_url?[c.source_url]:[])])].slice(-180);
    assetHistory.current=[...new Set([...assetHistory.current,...items.flatMap(c=>c?[c.id,c.source_asset_id].filter((id):id is string=>!!id&&/^[a-f0-9]{32}$/.test(id)):[])])].slice(-180);
    try{localStorage.setItem('rank-studio-sources',JSON.stringify(sourceHistory.current));localStorage.setItem('rank-studio-assets',JSON.stringify(assetHistory.current));}catch{}
  }
  function renderPreparedClips(items:Clip[],limit=maxDuration):Promise<Job>{
    if(window.rankDesktop&&!desktopAI.online&&voice&&voiceSettings.provider==='edge')throw new Error('Hlas Edge potřebuje internet. Pro offline export vyber stažený Piper nebo vypni voiceover.');
    if(voice&&!hasVoice)throw new Error('Vybraný hlas není připojený. Vyber Andrew / Antonín zdarma, nebo voiceover vypni.');
    if(items.reduce((sum,c)=>sum+c.duration,0)>limit+.000001)return Promise.reject(new Error(`Celé video smí mít nejvýše ${limit} sekund.`));
    return api<Job>('/render',{title:title.trim()||topic,ranking_criteria:criteria,clips:items,max_duration:limit,language,voice,effects,captions,resolution,layout,voice_settings:voiceSettings,original_volume:originalVolume,voice_volume:voiceVolume,effects_volume:effectsVolume});
  }
  function changeClip(index: number, changes: Partial<Clip>) {
    if(changes.start!==undefined||changes.duration!==undefined)changes={...changes,selection_version:changes.selection_version??'manual-v1',visual_review:null,review_required:true,effects_mode:'auto',effect_at:.5,effect_cues:[]};
    if((changes.start!==undefined||changes.duration!==undefined)&&clips[index]?.rank_note_auto)changes={...changes,rank_note:'',rank_note_auto:false};
    else if(changes.rank_note!==undefined)changes={...changes,rank_note_auto:false};
    if(changes.voiceover!==undefined)changes={...changes,narration_mode:'custom'};
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
        setClips(old => old.map((c, slot) => slot === targets[i] ? normalize(result,targets[i]) : c));
      }
      setToast('Klipy jsou připravené. Doplňte krátký voiceover.');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(''); setUploadIndex(null); if (fileInput.current) fileInput.current.value = ''; }
  }
  function chooseFiles(index: number | null) { uploadTarget.current = index; fileInput.current?.click(); }
  async function splitCompilation(file:File){
    if(occupied)return;
    if(ready&&!window.confirm('Nahradit aktuální klipy výřezy z kompilace?'))return;
    setBusy('Nahrávám kompilaci…');setError('');setPlaying(false);
    try{
      const form=new FormData();form.append('file',file);
      const source=await api<{id:string}>('/upload',form,true);
      setJob(await api<Job>('/compilation',{id:source.id,topic:topic||'Vlastní kompilace',mode:discoveryMode,ranking_criteria:criteria,blur_text:blurText,language,exclude_notes:clips.filter(Boolean).map(c=>c!.rank_note??'')}));
    }catch(error){setError((error as Error).message);}
    finally{setBusy('');if(compilationInput.current)compilationInput.current.value='';}
  }
  async function varyNotes(){
    if(occupied||!ready)return;setBusy('Předávám výřezy k vytvoření poznámek…');setError('');
    try{setJob(await api<Job>('/rank-notes',{language,clips:clips.filter(Boolean)}));}
    catch(e){setError((e as Error).message);}finally{setBusy('');}
  }
  async function cancelSearch(){
    if(!job)return;
    pendingSearchPreview.current=null;
    try{const result=await api<Job>(`/jobs/${job.id}/cancel`,{});if(!['done','failed'].includes(result.status))setJob(result);}catch(e){setError((e as Error).message);}
  }
  async function recutAll(){
    if(occupied||ready!==5)return;setPlaying(false);setError('');
    try{setJob(await api<Job>('/recut',{clips:clips.filter(Boolean)}));}catch(e){setError((e as Error).message);}
  }
  async function refreshLocalVision(){
    try{const state=await api<LocalVision>('/local-vision/status');setHealth(old=>old?{...old,local_vision:state}:old);if(state.ready){setDiscoveryMode('local');setLocalSetup(false);setToast('AI na tvém PC je připravená. Výběr poběží zdarma.');}else if(!state.setup_running)setLocalSetup(false);}
    catch(e){setError((e as Error).message);}
  }
  async function setupLocalVision(){
    setError('');setBusy('Otevírám přípravu AI zdarma…');
    try{const result=await api<{message:string}>('/local-vision/setup',{});setLocalSetup(true);setToast(result.message);}
    catch(e){setError((e as Error).message);}finally{setBusy('');}
  }
  async function chooseLocalModel(model:string){
    setError('');setBusy('Měním vizuální model…');
    try{const state=await api<LocalVision>('/local-vision/model',{model});setHealth(old=>old?{...old,local_vision:state}:old);setDiscoveryMode(state.ready?'local':'free');setToast(state.ready?`Model ${state.model} je připravený.`:`Vybrán ${state.model}. Klikni na Připravit vybranou AI zdarma.`);}
    catch(e){setError((e as Error).message);}finally{setBusy('');}
  }
  useEffect(()=>{if(!localSetup)return;const timer=setInterval(refreshLocalVision,5000);return()=>clearInterval(timer);},[localSetup]);
  async function cleanupClips(){
    if(occupied||ready!==5)return;setError('');setPlaying(false);
    pendingSearchPreview.current=autoPreview?renderPreparedClips:null;
    try{setJob(await api<Job>('/cleanup-clips',{clips:clips.filter(Boolean),mode:health?.local_vision?.ready?'local':'free'}));}
    catch(e){pendingSearchPreview.current=null;setError((e as Error).message);}
  }
  async function visualReview(){
    if(occupied||!ready)return;
    if(!window.rankDesktop&&!health?.local_vision?.ready){setError('Nejdřív vyber a ověř vizuální model v Nastavení AI.');document.getElementById('local-vision-panel')?.scrollIntoView({behavior:'smooth'});return;}
    if(topic.trim().length<3){setError('Pro vizuální posouzení napiš téma do Co dnes rankujeme.');return;}
    setPlaying(false);setError('');setBusy('Předávám originály k vizuálnímu AI posouzení…');
    pendingSearchPreview.current=autoPreview?renderPreparedClips:null;
    try{
      const result=await api<Job>('/visual-reselect',{mode:'local',clips:clips.filter(Boolean),topic,ranking_criteria:criteria,language,blur_text:blurText});
      setPreviousClips(clips);try{localStorage.setItem('rank-studio-previous-clips',JSON.stringify(clips));}catch{}
      setJob(result);
    }catch(e){pendingSearchPreview.current=null;setError((e as Error).message);}finally{setBusy('');}
  }
  async function openTrim(index:number,full=false){
    const c=clips[index];if(!c||occupied)return;setSelected(index);setPlaying(false);setBusy('Načítám původní záběr…');setError('');
    try{const context=await api<NonNullable<typeof trim>['context']>('/clip-context',{id:c.id,parent_id:c.source_asset_id,parent_start:c.source_start,start:c.start,duration:c.duration,full_source:full});setTrim({index,context});}
    catch(e){setError((e as Error).message);}finally{setBusy('');}
  }
  async function applyTrim(start:number,end:number,framing:Framing){
    if(!trim)return;const c=clips[trim.index]!;
    const a=await api<Record<string,unknown>>('/clip-cut',{id:c.id,parent_id:c.source_asset_id,parent_start:c.source_start,start:c.start,duration:c.duration,cut_start:start,cut_end:end,full_source:trim.context.full_source??false,framing,original_framing:c.framing??'fill',blur_regions:c.blur_regions??[]});
    changeClip(trim.index,{...normalize(a,trim.index),title:c.title,rank_note:c.rank_note,voiceover:c.voiceover,narration_mode:c.narration_mode,source_url:c.source_url});setTrim(null);setToast('Střih změněn. Zkontroluj pointu, zvuk a rozmazání v novém úseku.');
  }
  async function loadDemo() {
    if (ready && !window.confirm('Nahradit aktuální klipy syntetickou ukázkou?')) return;
    setError(''); setBusy('Připravuji pět ukázkových klipů…');
    try { const result = await api<{ clips: Record<string, unknown>[] }>('/demo', {}); setClips(result.clips.map((c,i)=>normalize(window.rankDesktop?{...c,sourceDuration:c.duration,start:0,duration:Math.min(4,maxDuration/5)}:c,i))); setTitle('TOP 5 COLOR REMIXES');setTitleFollowsTopic(false); setSelected(0); setToast('Syntetická ukázka načtena. Nejde o klipy z TikToku.'); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(''); }
  }
  async function discover() {
    if (!window.rankDesktop&&searchDepth==='thorough'&&!health?.local_vision?.ready) {setError('Pro důkladné hledání vyber a ověř vizuální AI model.');document.getElementById('local-vision-panel')?.scrollIntoView({behavior:'smooth'});return;}
    if (topic.trim().length < 3) { setError('Napište téma alespoň o třech znacích, například funny cats.'); return; }
    if (ready && !window.confirm('Nahradit aktuální klipy novým vyhledáváním?')) return;
    setError(''); setExported(null);setPlaying(false);setBusy('Zahajuji nové hledání…');
    rememberSources(clips);
    pendingSearchPreview.current=autoPreview?items=>renderPreparedClips(items,searchDepth==='thorough'?25:40):null;
    try { const result = await api<Job>('/discover', { topic, search_depth:searchDepth,max_duration:searchDepth==='thorough'?25:40, ranking_criteria: criteria, source: 'social', allow_youtube: allowYoutube, language, candidate_count: candidateCount, mode:window.rankDesktop&&searchDepth==='thorough'?'local':discoveryMode,blur_text:blurText,exclude_notes:clips.filter(Boolean).map(c=>c!.rank_note??''),exclude_urls:avoidRepeats?sourceHistory.current:[],exclude_asset_ids:avoidRepeats?assetHistory.current:[] });
      if(ready){setPreviousClips(clips);try{localStorage.setItem('rank-studio-previous-clips',JSON.stringify(clips));}catch{}}
      setClips(blankClips());setSelected(0);setRestored(false);setMaxDuration(searchDepth==='thorough'?25:40);setJob(result); }
    catch (e) { pendingSearchPreview.current=null;setError((e as Error).message); if (discoveryMode==='local')document.getElementById('local-vision-panel')?.scrollIntoView({behavior:'smooth'}); }
    finally{setBusy('');}
  }
  function restorePreviousClips(){
    if(!previousClips||occupied)return;
    setClips(previousClips);setMaxDuration(40);setPreviousClips(null);setSelected(0);setPlaying(false);setJob(null);setError('');setRestored(true);
    try{localStorage.removeItem('rank-studio-previous-clips');}catch{}setToast('Vráceny předchozí klipy. Nejde o výsledek nového hledání.');
  }
  async function generateScripts(mode:'ai'|'rank'='ai') {
    if (ready !== 5) { setError('Nejdřív připravte všech pět klipů.'); return; }
    if(clips.some(c=>c?.voiceover)&&!window.confirm('Nahradit současné komentáře novými krátkými větami?'))return;
    setBusy(mode==='rank'?'Připravuji krátká uvedení pořadí…':'AI píše komentáře do čtyř slov podle obrazu…'); setError('');
    try {
      const result = await api<{ lines: string[] }>('/scripts', { clips: clips.filter(Boolean), language, ranking_criteria: criteria, mode, max_words:4 });
      setClips(old => old.map((c, i) => c ? { ...c, voiceover: result.lines[i], narration_mode:mode==='rank'?'rank':'custom' } : c));
      if(mode==='rank')setVoiceSettings({...DEFAULT_VOICE});
      setVoice(true);setEffects(true);setCaptions(true);
      setToast(mode==='rank'?'Krátká uvedení pořadí připravena. Hlas zdarma a efekty jsou zapnuté.':'Komentáře do čtyř slov připravené. Hlas a efekty jsou zapnuté.');
    }
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
    if(overDuration){setError(`Celé video smí mít nejvýše ${maxDuration} sekund. Uprav střihy nebo vyber kratší celé momenty.`);return;}
    if (!title.trim()) { setError('Doplňte název videa.'); return; }
    if (clips.some(c => c && (words(c.voiceover) > 7 || (voice && words(c.voiceover) === 0)))) { setError('Každý zapnutý voiceover musí mít 1 až 7 slov.'); return; }
    if(clips.some(c=>c&&words(c.rank_note??'')>4)){setError('Poznámka u čísla smí mít nejvýše 4 slova.');return;}
    if (voice && !hasVoice) { setError('AI hlas zatím není dostupný. Otevřete nastavení hlasu; export bez hlasu lze ověřit jeho vypnutím.'); setModal('settings'); return; }
    try { setPlaying(false);voiceAudio.current?.pause();setExported(null); setJob(await api<Job>('/render', { title, ranking_criteria: criteria, clips, max_duration:maxDuration, language, voice, effects, captions, resolution, layout, voice_settings: voiceSettings, original_volume: originalVolume, voice_volume: voiceVolume, effects_volume: effectsVolume })); }
    catch (e) { setError((e as Error).message); }
  }
  async function doResearch() {
    setModal('research'); setBusy('Zkoumám ranking kanály na YouTube…'); setError('');
    try { setResearch(await api<Research>('/research', { topic: topic || 'ranking Shorts' })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(''); }
  }
  function saveProject() {
    try { localStorage.setItem('rank-studio-project', JSON.stringify({ clips, title, topic, titleFollowsTopic, criteria, allowYoutube, layout, voiceSettings, reference, language, voice, effects, captions, resolution, originalVolume, voiceVolume, effectsVolume, candidateCount, discoveryMode, searchDepth, maxDuration, blurText, autoPreview, avoidRepeats, templateMethod, templateInstructions })); setSaved(true); setRestored(true); setToast(window.rankDesktop?'Projekt uložen v aplikaci.':'Projekt uložen v tomto prohlížeči.'); }
    catch { setError('Prohlížeč nemohl projekt uložit.'); }
  }
  function resetProject() {
    if (ready && !window.confirm('Vymazat aktuální projekt? Nahrané soubory zůstanou na serveru.')) return;
    if(window.rankDesktop)desktopAPI('/projects',{state:collectState()}).catch(()=>setError('Zálohu projektu se nepodařilo uložit.'));
    pendingSearchPreview.current=null;setClips(blankClips());setSearchDepth(window.rankDesktop?'thorough':'quick');setMaxDuration(window.rankDesktop?25:40);setDiscoveryMode(window.rankDesktop?'local':'free');setVoice(true);setCandidateCount(window.rankDesktop?100:24);setAutoPreview(true);setAvoidRepeats(true); setLayout(DEFAULT_LAYOUT);setVoiceSettings(DEFAULT_VOICE);setReference(null);setTemplateInstructions('');setTemplateFrame(0);setTemplateMethod('free');setMessages([]); setTopic('');setTitleFollowsTopic(true); setCriteria('Surprise, timing and skill'); setTitle('TOP 5 UNEXPECTED MOMENTS'); setSelected(0); setPlaying(false); setElapsed(0); setJob(null); setExported(null); setError(''); localStorage.removeItem('rank-studio-project'); setRestored(false); setToast('Nový projekt je připravený.');
  }
  function moveClip(index: number, direction: number) {
    const target = index + direction;
    if (target < 0 || target > 4) return;
    setClips(old => { const next = [...old]; [next[index], next[target]] = [next[target], next[index]]; return next.map((c,i)=>c?.narration_mode==='rank'?{...c,voiceover:rankLine(i,language)}:c); });
    setSelected(target);
  }

  function applyProject(p:AIProject){
    if(p.avoid_repeats!==undefined)setAvoidRepeats(p.avoid_repeats);
    setTopic(p.topic);setTitle(p.title);setTitleFollowsTopic(p.title===p.topic);setCriteria(p.ranking_criteria);setLanguage(p.language);setResolution(p.resolution);setCandidateCount(p.candidate_count);setAllowYoutube(p.allow_youtube);setVoice(p.voice);setEffects(p.effects);setCaptions(p.captions);setOriginalVolume(p.original_volume);setVoiceVolume(p.voice_volume);setEffectsVolume(p.effects_volume);setLayout({...DEFAULT_LAYOUT,...p.layout});setVoiceSettings(p.voice_settings);const next:(Clip|null)[]=p.clips.map(normalize);while(next.length<5)next.push(null);setClips(next);setSelected(0);setPlaying(false);
  }
  function chooseVoice(id:string){const v=VOICES.find(v=>v.id===id);if(v)setVoiceSettings({...voiceSettings,provider:v.provider,voice:v.voice});}
  async function previewMaleVoice(){
    setBusy('Připravuji ukázku mužského hlasu…');setError('');
    try{const r=await api<{url:string}>('/voice-preview',{text:language==='en'?'That recovery turns failure into a win.':'Tohle načasování rozhodlo o vítězství.',language,voice_settings:voiceSettings});voiceAudio.current?.pause();const a=new Audio(r.url);voiceAudio.current=a;await a.play();}catch(e){setError((e as Error).message);}finally{setBusy('');}
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
    try{setJob(await api<Job>('/assistant',{message:command,history,reference_id:reference?.id??null,reference_instructions:reference?templateInstructions:null,state:{topic,title,ranking_criteria:criteria,language,resolution,candidate_count:candidateCount,allow_youtube:allowYoutube,avoid_repeats:avoidRepeats,voice,effects,captions,original_volume:originalVolume,voice_volume:voiceVolume,effects_volume:effectsVolume,layout,voice_settings:voiceSettings,clips:clips.filter(Boolean)}}));}
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
        <button className="rail-button" title="Zvukový mix" aria-label="Zvukový mix" onClick={() => setModal('audio')}><AudioLines size={21}/></button>
      </nav>
      <div className="rail-bottom"><button className="rail-button" title="Nastavení" aria-label="Nastavení" onClick={() => window.rankDesktop?desktopAI.open():setModal('settings')}><Settings2 size={21}/></button><div className="avatar">M</div></div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <a className="wordmark" href="/">rank<span>studio</span><span className="beta">ULTRA NOIR</span></a>
        <div className="breadcrumbs"><span>Projekty</span><span>/</span><strong>{restored?'Otevřený projekt':'Nový Short'}</strong></div>
        <DesktopTopbar/><div className="top-actions"><span className="save-status"><span className={saved ? 'dot green' : 'dot'}/>{saved ? 'Uloženo' : restored ? 'Projekt obnoven' : 'Nový projekt'}</span><button className="button secondary save-button" onClick={saveProject} disabled={occupied}><Save size={15}/> Uložit projekt</button>{health?.owner_login&&<form action="/auth/logout" method="post"><button className="button secondary save-button" disabled={occupied}>Odhlásit se</button></form>}</div>
      </header>
      <main>
        <section className="editor">
          <div className="studio-intro">
            <div><div className="eyebrow"><span className="tiny-spark"><Clapperboard size={13}/></span> TVŮJ PRACOVNÍ PROSTOR</div><h1>Střihové studio<span className="studio-version">2.0.9</span></h1><p>Najdi silné momenty. Dolaď střih. Vytvoř svůj Short.</p></div>
            <div className="project-summary"><strong>{time(clips.filter(Boolean).reduce((sum,c)=>sum+(c?.duration??0),0))}<small> / {maxDuration} s</small></strong><span>{ready} z 5 momentů · 9:16</span></div>
          </div>
          <DesktopAISetup/>
          <nav className="studio-workflow" aria-label="Pracovní postup">
            <button onClick={()=>document.getElementById('topic')?.focus()}><span>01</span><div><strong>Najít momenty</strong><small>Téma a zdroje</small></div><Search size={17}/></button>
            <button onClick={()=>document.querySelector('.clips-section')?.scrollIntoView({behavior:'smooth',block:'start'})}><span>02</span><div><strong>Doladit střih</strong><small>{ready}/5 klipů připraveno</small></div><Clapperboard size={17}/></button>
            <button onClick={()=>document.querySelector('.export-card')?.scrollIntoView({behavior:'smooth',block:'center'})}><span>03</span><div><strong>Exportovat</strong><small>Video ve tvém stylu</small></div><ArrowUpRight size={17}/></button>
          </nav>
          <details className="manual-controls" open><summary><Search size={13}/>Automatické hledání klipů<ChevronDown size={13}/></summary><div className="topic-box" data-search-depth={searchDepth}>
            <label htmlFor="topic"><Sparkles size={16}/> Co dnes rankujeme?</label>
            <div className="topic-input-row"><input id="topic" maxLength={100} value={topic} onChange={e => {setTopic(e.target.value);if(titleFollowsTopic)setTitle(e.target.value);}} onKeyDown={e => { if (e.key === 'Enter' && !occupied) discover(); }} placeholder="Například: ranking funniest cat moments" disabled={occupied}/><button className="button primary" onClick={discover} disabled={occupied}><WandSparkles size={16}/><span>Najít klipy</span><ArrowUpRight size={16}/></button></div>
            <div className="search-mode"><label htmlFor="search-mode">REŽIM HLEDÁNÍ</label><div className="select-wrap"><select id="search-mode" value={discoveryMode} disabled={occupied} onChange={e=>{setDiscoveryMode(e.target.value as 'free'|'local');if(e.target.value==='free')setSearchDepth('quick');}}><option value="free">Zdarma · technický výběr</option><option value="local" disabled={!window.rankDesktop&&!health?.local_vision?.ready}>{window.rankDesktop?'Vybraná AI':'AI na mém PC · zdarma'}{!window.rankDesktop&&!health?.local_vision?.ready?' · nejdřív připrav vizuální model':''}</option></select><ChevronDown size={12}/></div></div>
            {!window.rankDesktop&&<div className="local-vision-panel" id="local-vision-panel"><strong>AI na mém PC · zdarma</strong><p>{health?.local_vision?.message??'Ověřuji dostupnost lokální AI…'}</p>{health?.local_vision?.supported?<>
              <label htmlFor="local-model">Vizuální model</label><div className="select-wrap"><select id="local-model" value={health.local_vision.model} disabled={occupied||localSetup||health.local_vision.setup_running} onChange={e=>chooseLocalModel(e.target.value)}><option value="qwen2.5vl:7b">Qwen2.5-VL 7B · větší model</option><option value="qwen2.5vl:3b">Qwen2.5-VL 3B · úspornější</option></select><ChevronDown size={12}/></div>
              <button className="button secondary" disabled={occupied||localSetup} onClick={setupLocalVision}>{localSetup?'Příprava běží v samostatném okně…':'Připravit vybranou AI zdarma'}</button><button className="text-button" disabled={occupied} onClick={refreshLocalVision}>Ověřit AI</button>
              <small>7B: doporučeno 32 GB RAM. S 8 GB paměti grafiky může využít i RAM a být pomalejší. 3B šetří paměť. Příprava ověří RAM a disk; jednorázově stáhne několik GB.</small>
              {health.local_vision.memory&&<small>Načtený model: {(health.local_vision.memory.gpu_bytes/1024**3).toFixed(1)} GB v paměti grafiky z celkem {(health.local_vision.memory.total_bytes/1024**3).toFixed(1)} GB. Stav aktualizuje Ověřit AI.</small>}
            </>:<a href="http://127.0.0.1:8765/" target="_blank" rel="noreferrer">Otevřít studio na svém PC</a>}</div>}
            <label className="highlight-depth">Rozsah hledání<select aria-label="Rozsah hledání" disabled={occupied} value={searchDepth} onChange={e=>{const depth=e.target.value as 'quick'|'thorough';setSearchDepth(depth);if(depth==='thorough'){setDiscoveryMode('local');setCandidateCount(100);}else setCandidateCount(24);}}><option value="thorough">Důkladně · vizuální AI · nejvýše 25 s</option><option value="quick">Rychle · původní výběr</option></select></label>{searchDepth==='thorough'&&<p className="free-search-note">Až 100 odkazů · nejvýše 24 načtených videí · posouzení každého zdroje a hotových výřezů. Výsledek do 25 s, bez natahování. Analýza může trvat až 30 minut; cloud účtuje požadavky podle svého ceníku.</p>}
            <div className="criteria-input"><label htmlFor="criteria">TVŮJ ÚHEL POHLEDU</label><input id="criteria" value={criteria} maxLength={100} onChange={e=>setCriteria(e.target.value)} placeholder="Co porovnáváš? Např. surprise, timing, skill" disabled={occupied}/></div><div className="topic-options"><span className="social-sources"><Clapperboard size={12}/>TikTok + Instagram</span><label className="youtube-option"><input type="checkbox" checked={allowYoutube} onChange={e=>setAllowYoutube(e.target.checked)} disabled={occupied}/>+ YouTube</label><span className="option-divider"/><div className="select-wrap"><select aria-label="Počet kandidátů" value={candidateCount} onChange={e => setCandidateCount(Number(e.target.value))} disabled={occupied}><option value={8}>8 kandidátů</option><option value={12}>12 kandidátů</option><option value={20}>20 kandidátů</option><option value={24}>24 kandidátů</option><option value={40}>40 kandidátů</option><option value={80}>80 odkazů</option><option value={100}>100 odkazů</option></select><ChevronDown size={12}/></div><span className="topic-ai-note"><span className="dot green"/>{discoveryMode==='free'?'5 scén podle pravidel':'AI kontroluje děj a pointu'}</span></div>
            <div className="discovery-options"><label><input type="checkbox" checked={avoidRepeats} disabled={occupied} onChange={e=>setAvoidRepeats(e.target.checked)}/>Vynechat dříve použité zdroje</label><label><input type="checkbox" checked={autoPreview} disabled={occupied} onChange={e=>setAutoPreview(e.target.checked)}/>Po hledání vytvořit hotový náhled</label><label><input type="checkbox" checked={voice} disabled={occupied} onChange={e=>setVoice(e.target.checked)}/>Voiceover</label><label><input type="checkbox" checked={effects} disabled={occupied} onChange={e=>setEffects(e.target.checked)}/>Sound efekty</label></div>
            <label className="cleanup-option"><input type="checkbox" checked={blurText} disabled={occupied} onChange={e=>setBlurText(e.target.checked)}/> Automaticky rozmazat nápisy, emoji a malá loga</label><p className="compilation-help">Z kompilace se vybírají různé souvislé scény, každá jako samostatný výřez. Nahraná kompilace: nejvýše 10 minut / 300 MB.</p><button className="text-button" disabled={occupied} onClick={()=>compilationInput.current?.click()}><Upload size={13}/>Nahrát a rozstříhat kompilaci</button><input ref={compilationInput} type="file" accept="video/*" hidden onChange={e=>{const file=e.target.files?.[0];if(file)splitCompilation(file);}}/><p className="free-search-note">{discoveryMode==='free'?'Zdarma neověřuje děj ani pointu. Zachovává celé scény do 30 s v celkovém limitu 40 s; u delšího záběru výběr úseku s kontextem. Pointu zkontroluj přes Upravit střih. Zapnutý hlas uvede pořadí; vlastní komentář můžeš napsat u klipu. Hotový náhled přimíchá hlas a efekty podle přepínačů.':window.rankDesktop?`Vybraný model posuzuje časově označené snímky, ne původní zvuk. V cloudovém režimu se snímky odešlou vybranému poskytovateli; v lokálním zůstanou na PC. Může se splést. Nový výběr má nejvýše ${searchDepth==='thorough'?25:40} s; střih přehraj.`:'Lokální AI čte snímky přímo na tvém PC: téma, příprava, akce a výsledek. Střih 1–30 s podle děje. Bez API klíče, bez placených požadavků a bez odesílání snímků do cloudu. Limit 10 minut; na CPU může být pomalá. Neslyší původní zvuk a může se splést; střih přehraj.'}</p>
            <p className="free-search-note">{allowYoutube?searchDepth==='thorough'?'TikTok i Instagram hledáme souběžně, přes více dotazů a stránek veřejných výsledků. YouTube běží také přímo od začátku. Přístup k videu může síť omezit.':'TikTok i Instagram hledáme souběžně přes více stránek výsledků. YouTube doplní chybějící klipy. Omezení jednotlivých sítí uvidíš v přehledu.':'Hledáme na TikToku i Instagramu přes více dotazů a stránek výsledků. YouTube je vypnutý.'}</p>
            <SourceSessions disabled={occupied} onError={setError} local={!!health?.local_mode}/>
          </div>
          </details>
          {error && <div className="error-banner" role="alert"><Info size={16}/><span>{error}</span><button aria-label="Zavřít chybu" onClick={() => setError('')}><X size={15}/></button></div>}
          {job?.source_stats&&<section className="source-diagnostics" aria-label="Výsledky jednotlivých zdrojů"><div className="source-diagnostics-heading"><strong>Výsledky jednotlivých zdrojů</strong><span>{job.youtube_fallback?'Doplněno z YouTube':['done','failed'].includes(job.status)?'Hledání dokončeno':'Průběžný přehled'}</span></div><div className="source-stats">{Object.entries(job.source_stats).map(([name,row])=><article key={name} data-source={name}><div><span className="source-icon">{name==='TikTok'?'T':name==='Instagram'?'I':'Y'}</span><strong>{name}</strong></div><strong className="source-count">{row.downloaded}<small> / {row.found}</small></strong><p>načteno / nalezené odkazy</p>{row.reviewed!==undefined&&<small>{row.reviewed} posouzeno · {row.accepted??0} obsahově přijato</small>}{row.failed>0&&<small className="source-failed">{row.failed} se nepodařilo načíst</small>}{['done','failed'].includes(job.status)&&row.found===0&&<small className="source-failed">Žádné odpovídající odkazy ve veřejném indexu. Podrobnosti jsou níže.</small>}{job.download_failures?.some(f=>f.source===name&&f.kind==='login_required')&&<><small className="source-failed">Síť vyžaduje přihlášenou relaci.</small><button className="text-button" onClick={()=>{const panel=document.querySelector<HTMLDetailsElement>('.source-sessions');if(panel){panel.open=true;panel.scrollIntoView({behavior:'smooth',block:'center'});}}}>Přihlášení ke zdrojům</button></>}{job.download_failures?.some(f=>f.source===name&&f.kind==='blocked')&&<small className="source-failed">Síť omezuje přístup k videím z tohoto počítače.</small>}</article>)}</div>{!!(job.warnings?.length||job.download_failures?.length)&&<details><summary>Podrobnosti a nedostupné zdroje</summary>{job.warnings?.map((warning,index)=><p key={index}>{warning}</p>)}<ul>{job.download_failures?.map((failure,index)=><li key={index}><a href={failure.url} target="_blank" rel="noreferrer">{failure.source} · zdroj</a>: {failure.reason}</li>)}</ul></details>}</section>}

          {job?.warnings?.length&&!job.source_stats&&['done','failed'].includes(job.status)?<div className="compilation-help" role="status">{[...new Set(job.warnings)].map((note,i)=><p key={i}>{note}</p>)}</div>:null}
          {!!job?.search_results?.length && ['done','failed'].includes(job.status) && <details className="found-links"><summary><Search size={13}/>Nalezené zdroje ({job.search_results.length})</summary><p>Veřejné výsledky hledání. Některá videa nemusí jít automaticky stáhnout.</p>{job.search_results.map(result=><a key={result.url} href={result.url} target="_blank" rel="noreferrer">{result.title}<ArrowUpRight size={12}/></a>)}</details>}
          {job && !['done', 'failed'].includes(job.status) && <div className="job-card" role="status"><LoaderCircle size={18} className="spin"/><div><strong>{job.message}</strong>{job.kind==='discover'&&searchDepth==='thorough'&&<div className="search-stage-list"><span className={job.progress>=10?'complete':'active'}>Odkazy</span><span className={job.progress>=40?'complete':job.progress>=10?'active':''}>Načítání</span><span className={job.progress>=80?'complete':job.progress>=40?'active':''}>Posouzení AI</span><span className={job.progress>=80?'active':''}>Kontrola střihů</span></div>}{job.ai&&<small>Model této úlohy: {job.ai.model}</small>}{job.limit_seconds&&<small className="job-timing">{time(job.elapsed_seconds??0)} / {time(job.limit_seconds)} · celkový limit {job.kind==='visual-review'?'posouzení':job.kind==='cleanup'?'čištění':'hledání'}</small>}<div className="progress-track"><span style={{ width: `${job.progress}%` }}/></div></div><span>{job.progress}%</span>{['discover','visual-review','cleanup'].includes(job.kind??'')&&job.limit_seconds&&<button className="button secondary" onClick={cancelSearch} disabled={job.cancel_requested}>{job.cancel_requested?'Zastavuji…':job.kind==='visual-review'?'Zastavit posouzení':job.kind==='cleanup'?'Zastavit čištění':'Zastavit hledání'}</button>}</div>}
          {!!job?.downloaded_sources?.length&&job.status==='failed'&&<details className="found-links"><summary>Stažené zdroje ({job.downloaded_sources.length}) · výběr nedokončen</summary><p>Dokončená videa zůstala zachovaná. Tady můžeš přehrát celý zdroj; pointa není automaticky ověřená.</p>{job.downloaded_sources.map(source=><a key={String(source.id)} href={String(source.url)} target="_blank" rel="noreferrer">{String(source.name)}<ArrowUpRight size={12}/></a>)}</details>}
          {busy && <div className="busy-note" role="status"><LoaderCircle size={14} className="spin"/>{busy}</div>}
          <section className="clips-section">
            <div className="section-heading"><div><h2>Tvoje ranking klipy <span>{ready}<i>/5</i></span></h2><p>Od dobrého k nejlepšímu. Velké finále patří #1.</p></div><button className="text-button" disabled={occupied} onClick={() => chooseFiles(null)}><Upload size={14}/> Nahrát vlastní</button></div>
            <input ref={fileInput} type="file" multiple accept="video/*,.mp4,.mov,.webm,.mkv" className="hidden" onChange={e => e.target.files && upload(e.target.files, uploadTarget.current)}/>
            {previousClips?.some(Boolean)&&<div className="previous-clips-note"><span>Předchozí klipy jsou uložené zvlášť. Nové hledání je automaticky nepoužije.</span><button className="text-button" disabled={occupied} onClick={restorePreviousClips}>Vrátit předchozí klipy</button></div>}
            {legacyFourSecondCuts&&<div className="legacy-cuts-note" role="status"><strong>Tento projekt stále používá pět čtyřsekundových výřezů.</strong><p>Aktualizace aplikace uložené střihy sama nepřepsala. Obnov celé scény z originálů a zkontroluj jejich pointu.</p><button className="button secondary" disabled={occupied} onClick={recutAll}>Obnovit střihy z originálů</button></div>}
            <p className={`duration-budget ${overDuration?'over':''}`} role="status">Celé video: {clips.filter(Boolean).reduce((sum,c)=>sum+(c?.duration??0),0).toFixed(1)} / {maxDuration} s · maximální délka, kratší výsledek se nenatahuje.{overDuration?' Překročený limit: uprav střihy nebo vyber jiné celé momenty.':''}</p><label className="duration-limit">Limit tohoto projektu <input aria-label="Maximální délka projektu" type="number" min={5} max={MAX_PROJECT_SECONDS} step={1} disabled={occupied} value={durationDraft??maxDuration} onChange={e=>{const raw=e.target.value;setDurationDraft(raw);const value=Number(raw);if(value>=5&&value<=MAX_PROJECT_SECONDS)setMaxDuration(value);}} onBlur={()=>{if(durationDraft!==null)setMaxDuration(Math.max(5,Math.min(MAX_PROJECT_SECONDS,Number(durationDraft)||25)));setDurationDraft(null);}} onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur();}}/> s</label><div className="clip-list">
              {clips.map((clip, index) => <article key={index} className={`clip-card ${selected === index && clip ? 'selected' : ''} ${index === 4 ? 'winner' : ''}`} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (e.dataTransfer.files.length) upload(e.dataTransfer.files, index); }}>
                <div className="rank-block"><span className="rank-hash">#</span>{5-index}{index === 4 && <Trophy size={11}/>}</div>
                {clip ? <>
                  <button className="clip-thumb" onClick={() => { setSelected(index); setPlaying(false); setElapsed(clips.slice(0,index).reduce((s,c) => s + (c?.duration || 4),0)); }} aria-label={`Zobrazit klip ${5-index}`}><img src={clip.thumbnail} alt={clip.title}/><span><Play size={13} fill="currentColor"/></span><small>{clip.duration.toFixed(1)}s</small></button>
                  <div className="clip-content"><div className="clip-title-row"><input aria-label={`Název klipu ${5-index}`} maxLength={60} value={clip.title} onChange={e => changeClip(index, { title: e.target.value })}/><span className="ready-label"><Check size={10}/>Připraveno</span></div><label className="rank-note-input"><span>Poznámka u #{5-index}</span><input aria-label={`Poznámka u čísla ${5-index}`} value={clip.rank_note??''} maxLength={40} placeholder="Poznámka k tomuto ději · nejvýše 4 slova" onChange={e=>changeClip(index,{rank_note:e.target.value})}/><small>{words(clip.rank_note??'')}/4</small></label><label className="clip-end-audio" title="Automatika potlačí prudký hlasitý skok v poslední půlsekundě. Je-li zvuk součástí důležitého děje, zvol Ponechat. Obraz se nezkracuje.">Zvuk na konci<select aria-label={`Zvuk na konci klipu ${5-index}`} value={clip.end_audio??'auto'} disabled={occupied||clip.has_audio===false} onChange={e=>changeClip(index,{end_audio:e.target.value as Clip['end_audio']})}><option value="auto">Automaticky zjemnit hlasitý konec</option><option value="keep">Ponechat důležitý zvuk</option><option value="mute">Ztlumit posledních 0,5 s</option></select></label><ClipEffects value={clip} duration={clip.duration} rank={5-index} disabled={occupied} selected={selected===index} previewTime={()=>Math.max(0,(video.current?.currentTime??clip.start)-clip.start)} onChange={(value:Partial<EffectSettings>)=>changeClip(index,value)}/><div className={`voice-input ${words(clip.voiceover)>7 ? 'invalid' : ''}`}><Mic2 size={12}/><input aria-label={`Voiceover klipu ${5-index}`} maxLength={180} value={clip.voiceover} placeholder="Krátce: 2–4 slova. Nejvýše 7." onChange={e => changeClip(index,{voiceover:e.target.value})}/><button title="Poslechnout AI hlas" aria-label={`Poslechnout voiceover ${5-index}`} disabled={occupied || !clip.voiceover} onClick={() => playVoice(clip)}><Play size={12}/></button><span>{words(clip.voiceover)}<i>/7</i></span></div><div className="clip-meta"><label>Začátek <input type="number" min={0} max={Math.max(0,clip.sourceDuration-1)} step={0.1} value={Number(clip.start.toFixed(1))} aria-label={`Začátek klipu ${5-index}`} onChange={e => {const start=Math.max(0,Math.min(clip.sourceDuration-1,Number(e.target.value)));changeClip(index,{start,duration:Math.min(clip.duration,clip.sourceDuration-start)});if(index===selected&&video.current&&video.current.readyState>=1)video.current.currentTime=start;}}/>s</label><span>·</span><label>Délka <input type="number" min={1} max={Math.min(30,clip.sourceDuration-clip.start)} step={0.5} value={Number(clip.duration.toFixed(2))} aria-label={`Délka klipu ${5-index}`} onChange={e => changeClip(index,{duration:Math.max(1,Math.min(30,clip.sourceDuration-clip.start,Number(e.target.value)))})}/>s</label><button className="cleanup-clip-button" disabled={occupied} onClick={()=>openTrim(index)}>Upravit střih</button>{clip.has_audio===false&&<span className="source-silent">Zdroj bez zvuku</span>}{clip.review_required&&<span className="source-silent">{clip.visual_review?'AI posoudila snímky · přehraj střih':'Pointa neověřená'}</span>}<button className="cleanup-clip-button" disabled={occupied} onClick={()=>{setSelected(index);setPlaying(false);setCleanupIndex(index);}}>Rozmazání{clip.blur_regions?.length?` (${clip.blur_regions.length})`:""}</button>{clip.reason && <span title={clip.reason} className="ai-selected"><Sparkles size={10}/>Výběr scény</span>}{clip.source_url && <a href={clip.source_url} target="_blank" rel="noreferrer" title="Původní zdroj">Zdroj <ArrowUpRight size={9}/></a>}</div>{clip.visual_review&&<details className="visual-evidence"><summary>Co AI viděla ve scéně</summary>{clip.visual_review.model&&<p>Model posouzení: {clip.visual_review.model} · {clip.visual_review.provider}</p>}<p>Časy v původním zdroji. AI vyhodnotila obrazové vzorky; výsledek zkontroluj.</p>{(['setup','action','outcome'] as const).map((key,i)=><p key={key}><strong>{['Příprava','Hlavní moment','Výsledek'][i]} · {clip.visual_review![key].time.toFixed(1)} s:</strong> {clip.visual_review![key].observation}</p>)}</details>}</div>
                  <div className="clip-actions"><button aria-label={`Posunout klip ${5-index} nahoru`} disabled={index===0 || occupied} onClick={() => moveClip(index,-1)}><ArrowUp size={13}/></button><button aria-label={`Posunout klip ${5-index} dolů`} disabled={index===4 || occupied} onClick={() => moveClip(index,1)}><ArrowDown size={13}/></button><button aria-label={`Nahradit klip ${5-index}`} disabled={occupied} onClick={() => chooseFiles(index)}><RotateCcw size={12}/></button><button aria-label={`Odstranit klip ${5-index}`} disabled={occupied} onClick={() => {setClips(old=>old.map((c,i)=>i===index?null:c)); if(selected===index)setPlaying(false);}}><X size={12}/></button></div>
                </> : <button className="empty-clip" disabled={occupied} onClick={() => chooseFiles(index)}><span className="empty-thumb">{uploadIndex===index?<LoaderCircle size={19} className="spin"/>:<Plus size={21}/>}</span><span><strong>{index===4?'Vítězný moment':'Místo pro tvůj moment'}</strong><small>Přetáhni video nebo klikni pro nahrání</small></span><span className="empty-length">{searchDepth==='thorough'?'Hlavní moment':'1–30 s'}</span></button>}
              </article>)}
            </div>
            <div className="clip-footer"><span><ShieldCheck size={13}/>Jedna scéna. Žádné zbytečné čekání.</span><div className="comment-actions"><button className="text-button" disabled={occupied||ready!==5} onClick={cleanupClips}>Vyčistit všechny klipy</button><button className="text-button" disabled={occupied||!ready} onClick={visualReview}><Sparkles size={13}/>{window.rankDesktop?'Posoudit originály vybranou AI':health?.local_vision?.ready?'AI zdarma posoudit originály':'Připravit AI zdarma pro výběr'}</button><button className="text-button" disabled={occupied||ready!==5} onClick={recutAll}>Znovu vybrat celé scény</button><button className="text-button" disabled={occupied||!ready} onClick={varyNotes}>Poznámky podle klipů</button><button className="text-button" disabled={occupied || ready!==5} onClick={()=>generateScripts('rank')}><Mic2 size={13}/> Uvedení pořadí zdarma</button></div></div>
            <p className="comment-help">Zdarma: krátké uvedení „Number five.“ až „Number one.“. Komentář k ději napiš do řádku klipu; AI podle obrazu spustíš zdarma na svém PC po přípravě modelu.</p><button className="demo-button" disabled={occupied} onClick={loadDemo}><Play size={12}/> Jen si to prohlížíš? <span>Vyzkoušet syntetickou ukázku</span><ArrowUpRight size={13}/></button>
          </section>
          <TemplatePanel reference={reference} layout={layout} onLayout={setLayout} method={templateMethod} onMethod={setTemplateMethod} aiAvailable={!!window.rankDesktop&&!!health?.local_vision?.ready} instructions={templateInstructions} onInstructions={setTemplateInstructions} frame={templateFrame} onFrame={setTemplateFrame} input={referenceInput} onUpload={uploadReference} onAnalyze={analyzeReference} onSave={saveTemplate} onRemove={()=>{setReference(null);setTemplateInstructions('');setTemplateFrame(0);}} disabled={occupied}/>
          <ProjectExchange save={saveProject} disabled={occupied}/><DesktopWritingPanel history={messages} onAnswer={(prompt,text)=>{const id=crypto.randomUUID();setMessages(old=>[...old,{id:id+'-u',role:'user' as const,content:prompt},{id:id+'-a',role:'assistant' as const,content:text}]);}}/>
        </section>
        <aside className="preview-panel">
          <div className="preview-heading"><h2><span className="dot green"/>Náhled Shortu</h2><span className="preview-badge">9:16</span></div>
          <div className="phone" onClick={() => {if(current)setPlaying(!playing);}}>
            {current ? <video ref={video} key={current.url} src={current.url} style={{objectFit:current.framing==='fit'?'contain':'cover'}} poster={current.thumbnail} muted={muted} playsInline onLoadedMetadata={() => { if(video.current)video.current.currentTime=current.start; }} onTimeUpdate={updateTime} onEnded={() => {if(playing && selected<4 && clips[selected+1])setSelected(selected+1);else setPlaying(false);}} onError={() => setError('Náhled klipu není dostupný. Nahrajte jej znovu.')} /> : <div className="phone-art"><div className="art-grid"/><div className="orb orb-one"/><div className="orb orb-two"/><div className="phone-art-label"><Film size={21}/><span>Tvoje momenty.<br/>Tvoje pořadí.</span></div></div>}
            {current&&<BlurMasks regions={current.blur_regions}/>}
            <div className="phone-overlay" style={{fontFamily:fontFamily(layout.font),background:`linear-gradient(180deg,rgba(0,0,0,${layout.header_darkness}) 0%,transparent 29%,transparent 68%,rgba(0,0,0,.65))`}}><span className="phone-series">THE TOP FIVE</span><TitleOverlay title={title || 'TOP 5 MOMENTS'} layout={layout}/><RankingNumbers layout={layout} activeRank={5-selected} time={noteTime} notes={captions?Object.fromEntries(clips.map((c,i)=>[5-i,c?.rank_note??''])):{}}/></div>
            {current && !playing && <button className="phone-play" aria-label="Přehrát náhled" onClick={e => {e.stopPropagation();setPlaying(true);}}><Play size={23} fill="currentColor"/></button>}
          </div>
          <div className="playback"><button aria-label={playing?'Pozastavit':'Přehrát'} disabled={!current} onClick={() => setPlaying(!playing)}>{playing?<Pause size={16}/>:<Play size={16} fill="currentColor"/>}</button><span>{time(elapsed)}</span><div className="playback-track"><span style={{width:`${Math.min(100, elapsed/totalDuration*100)}%`}}/></div><span>{time(totalDuration)}</span><button aria-label={muted?'Zapnout zvuk':'Ztlumit'} onClick={() => setMuted(!muted)}>{muted?<VolumeX size={16}/>:<Volume2 size={16}/>}</button></div>
          <div className="timeline">{clips.map((c,i)=><button key={i} className={selected===i?'selected':''} onClick={()=>{setSelected(i);setPlaying(false);setElapsed(clips.slice(0,i).reduce((s,c)=>s+(c?.duration||4),0));}} aria-label={`Náhled pozice ${5-i}`} style={c?{backgroundImage:`linear-gradient(0deg, rgba(0,0,0,.6), rgba(0,0,0,.1)),url(${c.thumbnail})`}:undefined}><span>#{5-i}</span><small>{c?.duration??4}s</small></button>)}</div>
          <p className="preview-note">Tento přehrávač ukazuje střih a původní zvuk. Úpravu koncového zvuku, zapnutý voiceover a SFX uslyšíš v hotovém náhledu níže; po hledání se vytvoří automaticky, pokud je tato volba zapnutá.</p>
          {clips.some(c=>c&&safeBlurRegions(c.blur_regions).length!==(c.blur_regions?.length??0))&&<div className="compilation-help" role="status">Staré příliš velké masky jsou vypnuté.<button disabled={occupied} onClick={()=>setClips(old=>old.map(c=>c?{...c,blur_regions:safeBlurRegions(c.blur_regions)}:c))}>Odebrat přerostlé masky</button><button disabled={occupied||ready!==5} onClick={cleanupClips}>Přepočítat malé masky</button></div>}
          <div className="audio-preview-actions"><button className="button secondary" disabled={occupied||ready!==5} onClick={exportVideo}>Vytvořit náhled se zvukem</button><button className="text-button" disabled={occupied||ready!==5} onClick={()=>generateScripts('rank')}>Připravit voiceover zdarma</button></div>
          <VolumeSlider label="Původní zvuk" value={originalVolume} set={setOriginalVolume} max={1.5}/>
          {exported&&<section className="finished-preview" aria-label="Hotové video"><h3>Hotové video se zvukem</h3><video aria-label="Přehrávač hotového Shortu" src={exported.replace(/\/download$/,'/preview')} controls playsInline preload="metadata" onPlay={()=>{setPlaying(false);voiceAudio.current?.pause();}}/><p>Tento náhled obsahuje výsledný vzhled, zapnutý hlas a efekty.</p>{job?.effects_plan&&<details className="effects-timeline"><summary>Časování efektů</summary>{job.effects_plan.map(plan=><div key={plan.rank}><strong>Klip #{plan.rank}</strong><p>{plan.reason}</p>{plan.events.map((event,i)=><span key={i}>{event.at.toFixed(2)} s · {EFFECT_NAMES[event.kind]}{event.observation?` · ${event.observation}`:''} </span>)}<button disabled={occupied} onClick={()=>{const index=clips.findIndex(c=>c?.id===plan.asset_id&&c.start===plan.clip_start&&c.duration===plan.clip_duration);if(index>=0)changeClip(index,{effects_mode:'custom',effect_cues:plan.events.map(({kind,at,gain})=>({kind,at,gain}))});}}>Upravit plán klipu #{plan.rank}</button></div>)}</details>}</section>}

          <div className="output-settings"><div className="output-heading"><h2>Finální doladění</h2><button title="Zvukový mix" aria-label="Zvukový mix" onClick={()=>setModal('audio')}><SlidersHorizontal size={15}/></button></div><label className="video-title-label" htmlFor="video-title">NÁZEV VE VIDEU</label><input id="video-title" className="video-title-input" maxLength={100} value={title} disabled={occupied} onChange={e=>{setTitle(e.target.value);setTitleFollowsTopic(false);}}/><RankSettings layout={layout} onLayout={setLayout} disabled={occupied}/><TitleSettings title={title} layout={layout} onLayout={setLayout} followTopic={titleFollowsTopic} onFollowTopic={follow=>{setTitleFollowsTopic(follow);if(follow)setTitle(topic);}} width={resolution==='1080'?1080:720} disabled={occupied}/><label className="video-title-label voice-label" htmlFor="male-voice">MUŽSKÝ HLAS</label><div className="voice-choice-row"><div className="select-wrap"><select id="male-voice" disabled={occupied} value={`${voiceSettings.provider}:${voiceSettings.voice}`} onChange={e=>chooseVoice(e.target.value)}>{VOICES.filter(v=>v.provider==='edge'||v.provider==='piper').map(v=><option key={v.id} value={v.id}>{v.name}</option>)}</select><ChevronDown size={12}/></div><button className="voice-sample" title="Poslechnout mužský hlas" aria-label="Poslechnout mužský hlas" disabled={occupied} onClick={previewMaleVoice}><Play size={13}/></button></div>{voiceSettings.provider==='edge'?<p className="free-voice-note">{language==='en'?'Andrew · anglický mužský hlas':'Antonín · český mužský hlas'} · zdarma bez účtu a API klíče. Text se posílá online službě Microsoft Edge; dostupnost ověř ukázkou. Zvol „Uvedení pořadí zdarma“ nebo napiš vlastní komentář, ideálně 2–4 slova.</p>:!hasVoice&&health?.free_voice?<div className="free-voice-note">Vybraný hlas není připojený.<button className="text-button" onClick={()=>{setVoiceSettings({...DEFAULT_VOICE});setToast('Vybraný bezplatný hlas bez registrace a API klíče.');}}>Použít hlas zdarma</button></div>:null}<div className="setting-row"><span><Mic2 size={15}/>AI voiceover <small>{language==='en'?'English':'Čeština'}</small></span><Toggle value={voice} set={v=>{if(!occupied)setVoice(v);}} label="AI voiceover"/></div><div className="setting-row"><span><Zap size={15}/>Zvukové efekty</span><Toggle value={effects} set={v=>{if(!occupied)setEffects(v);}} label="Zvukové efekty"/></div><div className="setting-row"><span><Clapperboard size={15}/>Poznámky u čísel</span><Toggle value={captions} set={setCaptions} label="Poznámky u čísel"/></div><div className="format-settings"><div><label htmlFor="resolution">ROZLIŠENÍ</label><div className="select-wrap"><select id="resolution" value={resolution} onChange={e=>setResolution(e.target.value)}><option value="1080">1080 × 1920</option><option value="720">720 × 1280</option></select><ChevronDown size={12}/></div></div><div><label htmlFor="language">JAZYK HLASU</label><div className="select-wrap"><select id="language" disabled={occupied} value={language} onChange={e=>{const lang=e.target.value;setLanguage(lang);setClips(old=>old.map((c,i)=>c?.narration_mode==='rank'?{...c,voiceover:rankLine(i,lang)}:c));}}><option value="en">English</option><option value="cs">Čeština</option></select><ChevronDown size={12}/></div></div></div></div>
          <div className="export-card"><div><span><Film size={13}/>MP4 · H.264</span><span>{time(totalDuration)} · {resolution}p</span></div>{exported?<a className="button primary export-button" href={exported} download><Download size={17}/>Stáhnout Short<Check size={17}/></a>:<button className="button primary export-button" onClick={exportVideo} disabled={occupied||ready!==5||overDuration}>{occupied?<LoaderCircle className="spin" size={17}/>:<Download size={17}/>}Exportovat Short<ArrowUpRight size={17}/></button>}<p>Připraveno pro YouTube Shorts, Reels i TikTok.</p></div>

        </aside>
      </main>
      <footer className="app-footer"><span>Malé momenty. Velký replay.</span><span>RANK STUDIO <i>✦</i> MADE FOR SHORTS</span></footer>
    </div>
    {toast && <div className="toast" role="status"><Check size={16}/>{toast}<button onClick={()=>setToast('')} aria-label="Zavřít oznámení"><X size={14}/></button></div>}
    {trim&&clips[trim.index]&&<ClipTrimmer key={`${trim.index}:${trim.context.bounds.start}:${trim.context.bounds.end}`} onExpand={()=>openTrim(trim.index,true)} context={trim.context} framing={clips[trim.index]!.framing??'fill'} onClose={()=>setTrim(null)} onApply={applyTrim}/>}
    {cleanupIndex!==null&&clips[cleanupIndex]&&<ClipCleanup key={clips[cleanupIndex]!.id} clip={clips[cleanupIndex]!} rank={5-cleanupIndex} onClose={()=>setCleanupIndex(null)} onApply={regions=>{changeClip(cleanupIndex,{blur_regions:regions});setCleanupIndex(null);}} detect={()=>api('/blur-suggestions',{id:clips[cleanupIndex]!.id,start:clips[cleanupIndex]!.start,duration:clips[cleanupIndex]!.duration,framing:clips[cleanupIndex]!.framing})}/>}
    {modal && <div className="modal-backdrop" onClick={()=>setModal(null)}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onClick={e=>e.stopPropagation()}><div className="modal-head"><span className="modal-icon">{modal==='settings'?<Settings2 size={20}/>:modal==='audio'?<AudioLines size={20}/>:<Search size={20}/>}</span><button aria-label="Zavřít dialog" onClick={()=>setModal(null)}><X size={20}/></button></div><h2 id="modal-title">{modal==='settings'?'Připoj svůj tvůrčí workflow':modal==='audio'?'Ať každý moment zazní':'Co funguje na YouTube'}</h2>
      {modal==='settings' && <><p className="modal-intro">Tento editor používá bezplatné hledání, lokální vizuální AI a bezplatné hlasy. API klíč nepotřebuješ.</p><Integration name="Vizuální AI na tvém PC" code={`Ollama · ${health?.local_vision?.model??'qwen2.5vl:7b'}`} ready={!!health?.local_vision?.ready} text={health?.local_vision?.message??'Dostupnost ověř v části AI na mém PC.'}/><Integration name="Andrew / Antonín · online hlas zdarma" code="Bez registrace a API klíče" ready={!!health?.free_voice} text="Microsoft Edge. Anglický nebo český mužský hlas; text se odesílá Microsoftu. Dostupnost ověř ukázkou."/><Integration name="Lokální anglický AI hlas" code="python scripts/download_models.py --language en" ready={!!health?.voices.en} text="Piper / Lessac. Běží lokálně bez placeného klíče."/><button className="button primary" onClick={async()=>{try {setHealth(await api<Health>('/health'));setToast('Stav bezplatných nástrojů aktualizován.');}catch(e){setError((e as Error).message);}}}><RotateCcw size={15}/>Znovu ověřit připojení</button></>}
      {modal==='audio' && <><p className="modal-intro">Voiceover vede. Původní zvuk nech tiše pod ním, efekt zvýrazní konkrétní hlavní moment.</p>{voiceSettings.provider==='openai'?<label className="delivery-label">PROJEV HLASU<textarea value={voiceSettings.delivery} maxLength={300} onChange={e=>setVoiceSettings({...voiceSettings,delivery:e.target.value})}/></label>:<p className="modal-intro">Tento poskytovatel používá vlastní projev hlasu. Níže můžeš upravit tempo a hlasitost; textové pokyny k tónu nepoužívá.</p>}<label className="volume-slider"><span>Tempo hlasu<strong>{voiceSettings.speed.toFixed(2)}×</strong></span><input type="range" min={.85} max={1.2} step={.05} value={voiceSettings.speed} onChange={e=>setVoiceSettings({...voiceSettings,speed:Number(e.target.value)})}/></label><VolumeSlider label="AI voiceover" value={voiceVolume} set={setVoiceVolume} max={1.5}/><VolumeSlider label="Původní zvuk klipu" value={originalVolume} set={setOriginalVolume} max={1.5}/><VolumeSlider label="Zvukové efekty" value={effectsVolume} set={setEffectsVolume}/><div className="modal-note"><Zap size={16}/><span>Efekty se řídí hlavním momentem klipu. Čas můžeš doladit u klipu; hlas má při překryvu přednost. Krátká věta nechá prostor klipu. Hlas a efekty uslyšíš v hotovém náhledu po exportu.</span></div><button className="button primary" onClick={()=>setModal(null)}>Hotovo<Check size={15}/></button></>}
      {modal==='research' && <><p className="modal-intro">AI průzkum veřejných výsledků YouTube pro Aura Shorts a další ranking kanály. U každého zjištění zůstává odkaz na zdroj.</p>{busy?<div className="research-loading"><LoaderCircle className="spin" size={25}/><span>{busy}</span></div>:research?<><div className="research-results">{research.channels.map((c,i)=><a key={i} href={c.url} target="_blank" rel="noreferrer"><strong>{c.name}<ArrowUpRight size={14}/></strong><p>{c.observation}</p><small>{c.evidence}</small></a>)}</div><ul className="research-tips">{research.recommendations.map((r,i)=><li key={i}>{r}</li>)}</ul><div className="modal-note"><Info size={16}/><span>{research.limitations || 'Výsledky vycházejí z dostupných veřejných podkladů. Přesný hlas je nutné ověřit z videa.'}</span></div></>:<div className="modal-note"><Info size={16}/><span>{error || 'Výzkum vyžaduje připojené AI API. Klíč zadej bezpečně v nastavení prostředí.'}</span></div>}<button className="button secondary" disabled={occupied} onClick={doResearch}><Search size={15}/>Zopakovat výzkum</button></>}
    </section></div>}
  </div>;
}

function Toggle({ value, set, label }: { value: boolean; set: (v:boolean)=>void; label:string }) { return <button className={`toggle ${value?'on':''}`} onClick={()=>set(!value)} role="switch" aria-checked={value} aria-label={label}><span/></button>; }
function Integration({name,code,ready,text}:{name:string;code:string;ready:boolean;text:string}) { return <div className="integration"><div><strong>{name}</strong><span className={ready?'connected':'not-connected'}>{ready?<Check size={12}/>:<span className="dot"/>}{ready?'Připojeno':'Vyžaduje nastavení'}</span></div><p>{text}</p><code>{code}</code></div>; }
function VolumeSlider({label,value,set,max=1}:{label:string;value:number;set:(v:number)=>void;max?:number}) { return <label className="volume-slider"><span>{label}<strong>{Math.round(value*100)}%</strong></span><input type="range" min={0} max={max} step={0.01} value={value} onChange={e=>set(Number(e.target.value))}/></label>; }

bootstrapDesktop().then(()=>createRoot(document.getElementById('root')!).render(<React.StrictMode><DesktopAIProvider><App/></DesktopAIProvider></React.StrictMode>)).catch(()=>{const root=document.getElementById('root')!;root.textContent='Uložený projekt se nepodařilo bezpečně otevřít. Data nebyla přepsána.';const button=document.createElement('button');button.textContent='Otevřít datový adresář';button.onclick=()=>window.rankDesktop?.openData();root.appendChild(button);});
