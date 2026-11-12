"""Non-destructive access to original footage when an automatic cut needs review."""
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .cleanup import BlurRegion
from .scene_context import reframe_regions
from .timeline import MIN_CLIP_SECONDS
from . import work_budget as work

router=APIRouter(prefix='/api')


class ContextRequest(BaseModel):
    id: str
    parent_id: str | None = None
    full_source: bool = False
    parent_start: float | None = Field(default=None,ge=0,le=600,allow_inf_nan=False)
    start: float = Field(default=0,ge=0,le=600,allow_inf_nan=False)
    duration: float = Field(default=4,ge=MIN_CLIP_SECONDS,le=30,allow_inf_nan=False)


def context(body):
    from . import main as m
    clip=m.asset(body.id)
    if body.start+body.duration>clip['duration']+.1:
        raise HTTPException(400,'Vybraný úsek přesahuje délku klipu.')
    parent_id=clip.get('source_asset_id') or body.parent_id or body.id
    parent=m.asset(parent_id)
    origin=float(clip.get('source_start',body.parent_start or 0)) if parent_id!=body.id else 0
    # Older cuts may only have provenance saved in the editor. An unknown
    # boundary is shown honestly as the full original source, never invented.
    lower=float(clip.get('scene_start',0))
    upper=min(float(clip.get('scene_end',parent['duration'])),parent['duration'])
    if body.full_source:
        lower,upper=0,parent['duration']
    current_start=min(upper-MIN_CLIP_SECONDS,max(lower,origin+body.start))
    if parent.get('preview_framing')!='original':
        full=m.DATA/'media'/parent_id/'context-preview.mp4'
        if not full.is_file():
            temporary=full.with_name('context-'+m.uuid.uuid4().hex+'.mp4')
            try:
                m.ffmpeg('-i',str(full.parent/'source'),'-vf','scale=640:1138:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1',
                     '-c:v','libx264','-preset','ultrafast','-crf','28','-c:a','aac','-movflags','+faststart',str(temporary),timeout=360)
                temporary.replace(full)
            except Exception:
                raise HTTPException(400,'Původní náhled se nepodařilo připravit.') from None
            finally:
                temporary.unlink(missing_ok=True)
        parent={**parent,'url':f'/media/{parent_id}/context-preview.mp4','preview_framing':'original'}
    return {'source':parent,'full_source':body.full_source,'bounds':{'start':lower,'end':upper},
            'current':{'start':current_start,'end':min(upper,current_start+body.duration)},
            'message':'Zkontroluj přípravu, hlavní moment i konec. Výřez má 1–30 sekund; původní video zůstává zachované.'}


@router.post('/clip-context')
def get_context(body:ContextRequest):
    return context(body)


class CutRequest(ContextRequest):
    cut_start: float = Field(ge=0,le=600,allow_inf_nan=False)
    cut_end: float = Field(ge=MIN_CLIP_SECONDS,le=600,allow_inf_nan=False)
    framing: Literal['fit','fill'] = 'fit'
    original_framing: Literal['fit','fill'] = 'fill'
    blur_regions: list[BlurRegion] = Field(default_factory=list,max_length=8)


@router.post('/clip-cut')
def cut_clip(body:CutRequest):
    from . import main as m
    ctx=context(body)
    lower,upper=ctx['bounds']['start'],ctx['bounds']['end']
    length=body.cut_end-body.cut_start
    if not MIN_CLIP_SECONDS<=length<=30 or body.cut_start<lower or body.cut_end>upper+.01:
        raise HTTPException(400,'Výřez musí mít 1–30 sekund a zůstat v rámci této scény.')
    parent=ctx['source']
    old=m.asset(body.id)
    row={**parent,'title':old['name'][:60],'voiceover':'','start':body.cut_start,'duration':length,
         'selection_version':'manual-v1','visual_review':None,
         'sourceDuration':parent['duration'],'scene_start':lower,'scene_end':upper,'_cut_scene':True,
         'source_url':old.get('source_url',''),'framing':body.framing}
    try:
        result=m.materialize_scenes([row])[0]
        result['framing']=body.framing
        video=next(s for s in m.probe(m.DATA/'media'/parent['id']/'source')['streams'] if s['codec_type']=='video')
        result['blur_regions']=reframe_regions(body.blur_regions,video['width'],video['height'],body.original_framing,body.framing)
        return result
    except Exception:
        raise HTTPException(400,'Výřez se nepodařilo připravit. Původní klip zůstal zachovaný.') from None


class RecutRequest(BaseModel):
    clips: list[dict] = Field(min_length=5,max_length=5)


def recut_all(job_id, rows):
    from . import main as m
    created=[]
    windows_by_source={}
    seen=set()
    result=[]
    try:
        for index,row in enumerate(rows):
            m.set_job(job_id,status='working',progress=5+index*18,message=f'Obnovuji celou scénu klipu #{5-index}…')
            old=m.Clip.model_validate(row)
            ctx=context(ContextRequest(id=old.id,parent_id=row.get('source_asset_id'),parent_start=row.get('source_start'),start=old.start,duration=old.duration))
            parent=ctx['source']
            path=m.DATA/'media'/parent['id']/'source'
            if parent['id'] not in windows_by_source:
                windows_by_source[parent['id']]=m.scene_windows(path)
            midpoint=(ctx['current']['start']+ctx['current']['end'])/2
            options=[w for w in windows_by_source[parent['id']] if w.scene_start<=midpoint<w.scene_end]
            if not options:
                raise ValueError('Původní scénu se nepodařilo určit. Otevři Upravit střih a vyber pointu ručně.')
            window=options[0]
            identity=(parent['id'],window.shot)
            if identity in seen:
                raise ValueError('Dva klipy vedou na stejnou scénu. Zkontroluj je přes Upravit střih.')
            seen.add(identity)
            item={**parent,**old.model_dump(),'id':parent['id'],'name':parent['name'],
                  'selection_version':'whole-scene-v1','visual_review':None,
                  'start':window[0],'duration':window[1],'sourceDuration':parent['duration'],
                  'scene_start':window.scene_start,'scene_end':window.scene_end,'_cut_scene':True,
                  'review_required':True,'framing':'fit'}
            cut=m.materialize_scenes([item])[0]
            created.append(m.DATA/'media'/cut['id'])
            video=next(s for s in m.probe(path)['streams'] if s['codec_type']=='video')
            cut.update({key:getattr(old,key) for key in ('title','voiceover','narration_mode','rank_note','rank_note_auto','source_url','end_audio','effects_mode','effect_at')})
            if old.rank_note_auto:
                cut.update(rank_note='',rank_note_auto=False)
            cut['blur_regions']=reframe_regions(old.blur_regions,video['width'],video['height'],old.framing,'fit')
            result.append(cut)
        m.Project(title='Obnovené scény',clips=result,voice=False)
        m.set_job(job_id,status='done',progress=100,clips=result,message='Scény jsou znovu vybrané do 40 sekund. Přehraj je a zkontroluj pointu.')
    except Exception as error:
        for directory in created:
            m.shutil.rmtree(directory,ignore_errors=True)
        m.set_job(job_id,status='failed',message='Obnova střihu selhala: '+str(error)[:250])


@router.post('/recut',status_code=202)
def start_recut(body:RecutRequest):
    from . import main as m
    from pydantic import ValidationError
    try:
        validated=[m.Clip.model_validate(row) for row in body.clips]
        if len({clip.id for clip in validated})!=5:
            raise ValueError('Obnova potřebuje pět různých klipů.')
        body.clips=[{**raw,**clip.model_dump()} for raw,clip in zip(body.clips,validated)]
        for row in body.clips:
            m.asset(row['id'])
    except (ValueError,KeyError):
        raise HTTPException(422,'Obnova střihu potřebuje pět platných klipů.') from None
    with m.job_lock:
        if any(j['status'] in ('queued','rendering','searching','working') for j in m.jobs.values()):
            raise HTTPException(409,'Jeden úkol právě běží. Počkej na dokončení.')
        job_id=m.uuid.uuid4().hex
        m.jobs[job_id]={'id':job_id,'status':'queued','progress':0,'kind':'recut','message':'Připravuji původní scény…'}
    m.executor.submit(recut_all,job_id,body.clips)
    return dict(m.jobs[job_id])


class VisualReviewRequest(BaseModel):
    mode: Literal['local','ai'] = 'local'
    clips: list[dict] = Field(min_length=1,max_length=40)
    topic: str = Field(min_length=3,max_length=100)
    ranking_criteria: str = Field(default='Surprise, timing and skill',min_length=3,max_length=100)
    language: Literal['en','cs'] = 'en'
    blur_text: bool = True


def review_sources(rows):
    """Resolve retained originals, never judge only the old four-second cuts."""
    from . import main as m
    sources={}
    for row in rows:
        meta=m.asset(row['id'])
        seen=set()
        parent=meta.get('source_asset_id') or row.get('source_asset_id')
        while parent:
            if parent in seen or len(seen)>=10:
                raise ValueError('Návaznost původního videa není platná.')
            seen.add(parent)
            meta=m.asset(parent)
            parent=meta.get('source_asset_id')
        if not (m.DATA/'media'/meta['id']/'source').is_file():
            raise ValueError('Původní video už není uložené. Nahraj originál znovu.')
        sources[meta['id']]=meta
    return list(sources.values())


@work.limited_discovery
def visual_reselect(job_id,body):
    from . import main as m
    sources=[]
    try:
        m.set_job(job_id,status='working',progress=5,message='Načítám celé původní zdroje pro vizuální AI…')
        sources=review_sources(body.clips)
        clips=m.select_candidates(sources,body.topic,body.language,body.ranking_criteria,body.mode)
        warnings=[]
        if body.blur_text:
            m.add_cleanup(clips,warnings)
        m.set_job(job_id,status='done',progress=100,clips=clips,warnings=warnings,
                  message='AI posoudila obraz a vybrala nové střihy. Přehraj je a zkontroluj pointy i pořadí.')
    except work.WorkStopped as error:
        m.set_job(job_id,status='failed',progress=100,cancelled=error.cancelled,
                  message=str(error)+' Předchozí střihy zůstaly v editoru.',downloaded_sources=sources)
    except Exception as error:
        # Keep the old project untouched on incomplete or failed visual review.
        detail=str(error)[:300] if isinstance(error,ValueError) else 'Původní zdroj nebo AI služba není dostupná.'
        m.set_job(job_id,status='failed',message=detail+' Předchozí střihy zůstaly v editoru.',downloaded_sources=sources)


@router.post('/visual-reselect',status_code=202)
def start_visual_review(body:VisualReviewRequest):
    from . import main as m
    from pydantic import ValidationError
    if body.mode=='local':
        try:m.local_vision.require_ready()
        except ValueError as error:raise HTTPException(409,str(error)) from None
    if body.mode=='ai' and not m.health()['ai_scripts']:
        raise HTTPException(409,'AI sledování videí potřebuje připojené placené OpenAI API. Klíč nastav bezpečně na serveru, neposílej ho do chatu.')
    try:
        for row in body.clips:
            m.Clip.model_validate(row)
            m.asset(row['id'])
    except (ValidationError,KeyError):
        raise HTTPException(422,'Vizuální posouzení potřebuje platné uložené klipy.') from None
    with m.job_lock:
        if any(j['status'] in ('queued','rendering','searching','working') for j in m.jobs.values()):
            raise HTTPException(409,'Jeden úkol právě běží. Počkej na dokončení.')
        identity=m.uuid.uuid4().hex
        m.jobs[identity]={'id':identity,'status':'queued','progress':0,'kind':'visual-review','mode':body.mode,
                          'message':'Připravuji vizuální posouzení původních videí…','limit_seconds':work.LOCAL_SEARCH_SECONDS if body.mode=='local' else work.SEARCH_SECONDS}
        work.reserve(identity,work.LOCAL_SEARCH_SECONDS if body.mode=='local' else work.SEARCH_SECONDS)
    m.executor.submit(visual_reselect,identity,body)
    return dict(m.jobs[identity])


class CleanupBatchRequest(BaseModel):
    clips:list[dict]=Field(min_length=5,max_length=5)
    mode:Literal['free','local']='free'


@work.limited_discovery
def cleanup_batch(identity,body):
    from . import main as m
    try:
        rows=[]
        for raw in body.clips:
            clip=m.Clip.model_validate(raw)
            meta=m.asset(clip.id)
            rows.append({**meta,**raw,**clip.model_dump(),'url':meta['url'],'thumbnail':meta['thumbnail']})
        warnings=[]
        m.set_job(identity,status='working',progress=5,message='Čistím obraz vybraných klipů, střihy zůstávají zachované…')
        m.add_cleanup(rows,warnings)
        m.set_job(identity,status='done',progress=100,clips=rows,warnings=warnings,
                  message='Úpravy obrazu jsou připravené. Zkontroluj masky; časy střihů se nezměnily.')
    except work.WorkStopped as error:
        m.set_job(identity,status='failed',cancelled=error.cancelled,progress=100,
                  message=('Čištění bylo zastaveno.' if error.cancelled else 'Čištění překročilo časový limit.')+' Dosavadní klipy zůstaly v editoru.')
    except Exception:
        m.set_job(identity,status='failed',message='Čištění se nepodařilo dokončit. Dosavadní klipy zůstaly v editoru; další oblasti označ ručně.')


@router.post('/cleanup-clips',status_code=202)
def start_cleanup_batch(body:CleanupBatchRequest):
    from . import main as m
    try:
        identities=set()
        for raw in body.clips:
            clip=m.Clip.model_validate(raw);meta=m.asset(clip.id)
            if clip.start+clip.duration>meta['duration']+.05:
                raise ValueError('Výřez je mimo zdrojové video.')
            identities.add(clip.id)
        if len(identities)!=5:raise ValueError('Použij pět různých klipů.')
    except (ValueError,KeyError) as error:
        raise HTTPException(422,str(error)[:250]) from None
    with m.job_lock:
        if any(j['status'] in ('queued','rendering','searching','working') for j in m.jobs.values()):
            raise HTTPException(409,'Jeden úkol právě běží. Počkej na dokončení.')
        identity=m.uuid.uuid4().hex
        limit=work.LOCAL_SEARCH_SECONDS if body.mode=='local' else work.SEARCH_SECONDS
        m.jobs[identity]={'id':identity,'status':'queued','progress':0,'kind':'cleanup','limit_seconds':limit,
                          'message':'Připravuji čištění vybraných klipů…'}
        work.reserve(identity,limit)
    m.executor.submit(cleanup_batch,identity,body)
    return dict(m.jobs[identity])
