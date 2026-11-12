import uuid
import wave

import numpy as np
import pytest
from PIL import Image

from backend import main as m,cleanup as cleanup
from backend.blur_safety import safe_regions,narrow
from backend.overlay_geometry import join_rows
from backend.sound_design import plan_effects,render_effects,motion_moment
from test_workflow import isolated,make_source


def clip(**kwargs):
    return m.Clip(id='a'*32,title='Moment',voiceover='',duration=4,**kwargs)


def reviewed(**kwargs):
    return clip(visual_review={'confidence':.95,'setup':{'time':11,'observation':'Setup'},
      'action':{'time':12.6,'observation':'Action'},'outcome':{'time':13.5,'observation':'Result'}},start=.5,**kwargs)


def test_malformed_ocr_baselines_never_become_large_horizontal_strips():
    rows=join_rows([[(30,240,180,32),(230,241,110,31),(40,640,220,35),(30,300,650,200)]])
    assert len(rows)==2 and all(bottom-top<40 for _,top,_,bottom in rows)


def test_legacy_bands_are_disabled_and_explicit_large_manual_masks_remain_possible():
    bands=[m.BlurRegion(x=.04,y=.2,w=.9,h=.18,origin='auto'),m.BlurRegion(x=0,y=.6,w=1,h=.2)]
    assert safe_regions(bands)==[]
    assert cleanup.blur_filters(bands,720,1280)==([], 'source_clean')
    explicit=bands[1].model_copy(update={'allow_large':True})
    assert safe_regions([explicit])==[explicit]
    small=[m.BlurRegion(x=.1,y=.1+i*.08,w=.7,h=.04,origin='auto',kind='text') for i in range(7)]
    accepted=safe_regions(small)
    assert sum(r.w*r.h for r in accepted)<=.085
    assert all(narrow(r) for r in accepted)


def test_ai_bands_and_blocks_are_rejected_even_with_high_confidence(monkeypatch):
    monkeypatch.delenv('RANK_DESKTOP_MODE',raising=False)
    monkeypatch.setattr(m.local_vision,'status',lambda:{'ready':True})
    monkeypatch.setattr(m.local_vision,'request',lambda *args:{'regions':[
      {'x':0,'y':.2,'w':1,'h':.18,'kind':'text','method':'blur','confidence':1,'seen_frames':3},
      {'x':.1,'y':.6,'w':.8,'h':.1,'kind':'block','method':'remove','confidence':1,'seen_frames':3},
      {'x':.1,'y':.3,'w':.6,'h':.035,'kind':'text','method':'blur','confidence':.96,'seen_frames':3}]})
    regions,_=cleanup.vision_regions([Image.new('RGB',(720,1280))]*3,(0,0,1,1))
    assert len(regions)==1 and regions[0]['bottom']-regions[0]['y']<.04


def test_visual_action_uses_original_source_offset_and_preserves_native_impact(monkeypatch):
    monkeypatch.setattr('backend.sound_design.source_levels',lambda *args:np.zeros(200))
    plan=plan_effects(reviewed(),{'source_start':10,'has_audio':False},None,4)
    assert plan['source']=='visual' and len(plan['events'])==2
    assert all(abs(e['at']-2.1)<.001 for e in plan['events'])
    assert all(e['start']>1.8 for e in plan['events'])
    monkeypatch.setattr('backend.sound_design.source_levels',lambda *args:np.full(200,.3))
    plan=plan_effects(reviewed(),{'source_start':10,'has_audio':True},None,4)
    assert all(e['kind']!='accent' for e in plan['events'])
    assert len(plan['events'])<=1
    muted=plan_effects(reviewed(),{'source_start':10,'has_audio':True},None,4,original_gain=0)
    assert any(e['kind']=='accent' for e in muted['events'])


def test_no_arbitrary_intro_effect_and_manual_time_wins(monkeypatch):
    monkeypatch.setattr('backend.sound_design.motion_moment',lambda *args:None)
    assert plan_effects(clip(),{},None,5)['events']==[]
    plan=plan_effects(reviewed(effects_mode='manual',effect_at=1.4),{},None,5)
    assert plan['source']=='manual' and all(abs(e['at']-1.4)<.001 for e in plan['events'])
    assert plan_effects(clip(effects_mode='off'),{},None,1)['events']==[]


def test_real_motion_hint_ignores_flash_but_detects_local_late_action(isolated):
    local=isolated/'local.mp4';flash=isolated/'flash.mp4'
    m.ffmpeg('-f','lavfi','-i','color=c=blue:s=192x192:r=16:d=4','-vf',"drawbox=x=70:y=70:w=40:h=40:color=white:t=fill:enable='gte(t,2)'",'-c:v','libx264',str(local))
    m.ffmpeg('-f','lavfi','-i','color=c=blue:s=192x192:r=16:d=4','-vf',"drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='gte(t,2)'",'-c:v','libx264',str(flash))
    assert abs(motion_moment(local,0,4)-2)<.2
    assert motion_moment(flash,0,4) is None


def test_synthesized_effects_peak_at_event_and_duck_under_voice(isolated,monkeypatch):
    monkeypatch.setattr('backend.sound_design.source_levels',lambda *args:np.zeros(0))
    plan=plan_effects(clip(effects_mode='manual',effect_at=2.1),{},None,5)
    clean=isolated/'clean.wav';ducked=isolated/'ducked.wav'
    render_effects(clean,4,plan,5);render_effects(ducked,4,plan,5,(1.8,2.4))
    def samples(path):
        with wave.open(str(path),'rb') as w:return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)
    a,b=samples(clean),samples(ducked)
    assert np.max(abs(a[:int(1.8*44100)]))==0
    assert abs(a[int(2.08*44100):int(2.16*44100)]).mean()>500
    assert abs(b).sum()<abs(a).sum()*.5
    assert len(a)==4*44100


def test_real_export_skips_saved_bands_and_places_sfx_at_late_moment(isolated):
    clips=[]
    for i in range(5):
        meta=make_source(isolated/'media'/uuid.uuid4().hex,'blue',duration=3)
        clips.append({**meta,'title':'Moment','voiceover':'','start':0,'duration':3,
          'effects_mode':'manual','effect_at':2,'blur_regions':[{'x':0,'y':.2,'w':1,'h':.2,'origin':'auto'}]})
    project=m.Project(title='PRECISE',clips=clips,voice=False,effects=True,resolution='720')
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity};m.render(identity,project)
    job=m.jobs[identity];assert job['status']=='done',job
    assert len(job['warnings'])==5 and all(len(p['events'])<=2 for p in job['effects_plan'])
    path=isolated/'jobs'/identity/'ranking.mp4'
    raw=m.ffmpeg('-i',str(path),'-vn','-ac','1','-ar','44100','-f','f32le','pipe:1');audio=np.frombuffer(raw,dtype='<f4')
    for i in range(5):
        assert np.abs(audio[round((i*3+.1)*44100):round((i*3+1.5)*44100)]).max()<.001
        assert np.abs(audio[round((i*3+1.96)*44100):round((i*3+2.12)*44100)]).mean()>.005
    assert abs(float(m.probe(path)['format']['duration'])-15)<.08
