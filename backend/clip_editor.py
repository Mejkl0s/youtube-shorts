"""Non-destructive access to original footage when an automatic cut needs review."""
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .cleanup import BlurRegion
from .scene_context import reframe_regions

router=APIRouter(prefix='/api')


class ContextRequest(BaseModel):
    id: str
    parent_id: str | None = None
    full_source: bool = False
    parent_start: float | None = Field(default=None,ge=0,le=600,allow_inf_nan=False)
    start: float = Field(default=0,ge=0,le=600,allow_inf_nan=False)
    duration: float = Field(default=4,ge=2,le=30,allow_inf_nan=False)


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
    current_start=min(upper-2,max(lower,origin+body.start))
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
            'message':'Zkontroluj přípravu, hlavní moment i konec. Výřez má 2–30 sekund; původní video zůstává zachované.'}


@router.post('/clip-context')
def get_context(body:ContextRequest):
    return context(body)


class CutRequest(ContextRequest):
    cut_start: float = Field(ge=0,le=600,allow_inf_nan=False)
    cut_end: float = Field(ge=2,le=600,allow_inf_nan=False)
    framing: Literal['fit','fill'] = 'fit'
    original_framing: Literal['fit','fill'] = 'fill'
    blur_regions: list[BlurRegion] = Field(default_factory=list,max_length=8)


@router.post('/clip-cut')
def cut_clip(body:CutRequest):
    from . import main as m
    ctx=context(body)
    lower,upper=ctx['bounds']['start'],ctx['bounds']['end']
    length=body.cut_end-body.cut_start
    if not 2<=length<=30 or body.cut_start<lower or body.cut_end>upper+.01:
        raise HTTPException(400,'Výřez musí mít 2–30 sekund a zůstat v rámci této scény.')
    parent=ctx['source']
    old=m.asset(body.id)
    row={**parent,'title':old['name'][:60],'voiceover':'','start':body.cut_start,'duration':length,
         'selection_version':'manual-v1',
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
                  'selection_version':'whole-scene-v1',
                  'start':window[0],'duration':window[1],'sourceDuration':parent['duration'],
                  'scene_start':window.scene_start,'scene_end':window.scene_end,'_cut_scene':True,
                  'review_required':True,'framing':'fit'}
            cut=m.materialize_scenes([item])[0]
            created.append(m.DATA/'media'/cut['id'])
            video=next(s for s in m.probe(path)['streams'] if s['codec_type']=='video')
            cut.update({key:getattr(old,key) for key in ('title','voiceover','narration_mode','rank_note','source_url')})
            cut['blur_regions']=reframe_regions(old.blur_regions,video['width'],video['height'],old.framing,'fit')
            result.append(cut)
        m.set_job(job_id,status='done',progress=100,clips=result,message='Scény jsou znovu vybrané. Přehraj je a zkontroluj pointu; u dlouhého záběru pomůže Upravit střih.')
    except Exception as error:
        for directory in created:
            m.shutil.rmtree(directory,ignore_errors=True)
        m.set_job(job_id,status='failed',message='Obnova střihu selhala: '+str(error)[:250])


@router.post('/recut',status_code=202)
def start_recut(body:RecutRequest):
    from . import main as m
    from pydantic import ValidationError
    try:
        validated=m.Project(title='Obnova střihu',clips=body.clips,voice=False)
        body.clips=[{**raw,**clip.model_dump()} for raw,clip in zip(body.clips,validated.clips)]
        for row in body.clips:
            m.asset(row['id'])
    except (ValidationError,KeyError):
        raise HTTPException(422,'Obnova střihu potřebuje pět platných klipů.') from None
    with m.job_lock:
        if any(j['status'] in ('queued','rendering','searching','working') for j in m.jobs.values()):
            raise HTTPException(409,'Jeden úkol právě běží. Počkej na dokončení.')
        job_id=m.uuid.uuid4().hex
        m.jobs[job_id]={'id':job_id,'status':'queued','progress':0,'kind':'recut','message':'Připravuji původní scény…'}
    m.executor.submit(recut_all,job_id,body.clips)
    return dict(m.jobs[job_id])
