import json
import uuid
import wave

import numpy as np
import pytest

from backend import main as m,sound_director as d
from backend.sound_design import plan_effects,render_effects
from test_workflow import isolated,make_source


def proposals():
    return [{'time':at,'role':role,'effect':d.ROLE_EFFECT[role],'confidence':.96,'observation':note}
      for at,role,note in [(.7,'motion','Viditelný pohyb.'),(1.4,'reveal','Objeví se nový tvar.'),
                           (2.1,'stop','Pohyb se náhle zastaví.'),(3.2,'resolution','Je vidět výsledek.')]]


def test_roles_select_appropriate_effect_and_reject_guesses_and_bad_time():
    for p in proposals():assert d.validate_beat(p,4)
    for patch in [{'effect':'chime'},{'role':'invented'},{'time':float('nan')},{'time':-.2},{'confidence':.5},{'observation':''}]:
        assert d.validate_beat({**proposals()[0],**patch},4) is None
    assert d.validate_beat({**proposals()[0],'time':3.8},4,0,1) is None


def test_more_than_two_distinct_beats_allowed_without_machine_gun_repetition():
    events=[d.validate_beat(p,4) for p in proposals()]
    assert len(d.balance_events(events,4))==4
    repeated=[{**events[1],'at':t,'start':t-.02} for t in (1,1.1,1.2,1.3,1.5)]
    assert len(d.balance_events(repeated,4))==1
    assert sum(e['duration'] for e in d.balance_events(events*4,4))<=1.8


def test_preparation_can_resolve_into_one_accent_at_the_same_event():
    a=d.validate_beat({'time':2,'role':'anticipation','effect':'rise','confidence':.96,'observation':'Preparation ends at contact.'},4)
    b=d.validate_beat({'time':2,'role':'contact','effect':'accent','confidence':.96,'observation':'Visible contact.'},4)
    assert len(d.balance_events([a,b,b],4))==2


def test_real_frames_verified_in_small_batches_and_cached_per_cut_and_model(isolated,monkeypatch):
    meta=make_source(isolated/'media'/uuid.uuid4().hex,'blue',duration=5)
    clip=m.Clip(id=meta['id'],title='Untrusted title',voiceover='',duration=4)
    selection={'provider':'local','endpoint':'http://127.0.0.1:9999/v1','model':'fixture-model'}
    monkeypatch.setattr(d,'available_selection',lambda:dict(selection))
    calls=[]
    def request(prompt,evidence,tokens):
        assert any(b['type']=='image_url' for b in evidence)
        assert 'Untrusted title' not in prompt
        calls.append(prompt)
        if 'SCOUT.' in prompt:return {'beats':proposals()}
        details=[b['text'] for b in evidence if b['type']=='text']
        result=[]
        for text in details:
            identity=int(text.split(':')[0].split()[-1])
            beat=json.loads(text.split(': ',1)[1].split('. Check actual',1)[0])
            result.append({'candidate':identity,'accepted':True,'time':beat['at'],'role':beat['role'],
                           'effect':beat['kind'],'observation':beat['observation'],'confidence':.96})
        assert len(result)<=2
        return {'beats':result}
    monkeypatch.setattr(m.local_vision,'request',request)
    path=isolated/'media'/clip.id/'source'
    events,_=d.directed_events(clip,meta,path)
    assert len(events)==4 and len(calls)==3
    assert d.directed_events(clip,meta,path)[0]==events and len(calls)==3
    clip.start=.1;assert len(d.directed_events(clip,meta,path)[0])==4 and len(calls)==6
    selection['model']='second-model';d.directed_events(clip,meta,path);assert len(calls)==9
    assert len(list((isolated/'private/sound-plans').glob('*.json')))==3


def test_uncertain_visual_beats_are_rejected_without_filling_slots(isolated,monkeypatch):
    meta=make_source(isolated/'media'/uuid.uuid4().hex,'blue',duration=4)
    clip=m.Clip(id=meta['id'],title='Moment',voiceover='',duration=4)
    monkeypatch.setattr(d,'available_selection',lambda:{'provider':'local','endpoint':'http://127.0.0.1:9999','model':'m'})
    monkeypatch.setattr(m.local_vision,'request',lambda prompt,*args:{'beats':proposals()} if 'SCOUT.' in prompt else {'beats':[{'candidate':0,'accepted':False}]})
    assert d.directed_events(clip,meta,isolated/'media'/clip.id/'source')[0]==[]


def test_cache_identity_never_includes_provider_key(monkeypatch):
    from backend import desktop_ai
    monkeypatch.setenv('RANK_DESKTOP_MODE','1')
    monkeypatch.setattr(desktop_ai,'selected',lambda:{'vision':True,'model':'m','key':'PRIVATE_FIXTURE',
      'profile':{'id':'local','endpoint':'http://127.0.0.1:9999'}})
    assert 'PRIVATE_FIXTURE' not in json.dumps(d.available_selection())


def test_custom_multiple_cues_and_every_waveform_are_rendered(isolated):
    cues=[{'kind':p['effect'],'at':p['time'],'gain':.7} for p in proposals()]
    clip=m.Clip(id='a'*32,title='Moment',voiceover='',duration=4,effects_mode='custom',effect_cues=cues)
    plan=plan_effects(clip,{},None,5)
    assert len(plan['events'])==4
    path=isolated/'multiple.wav';render_effects(path,4,plan,5)
    with wave.open(str(path),'rb') as audio:samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2')
    for event in plan['events']:
        section=samples[round(event['start']*44100):round((event['start']+event['duration'])*44100)]
        assert abs(section.astype(float)).mean()>100
    for kind,at in [('rise',.8),('accent',1.6)]:
        custom=clip.model_copy(update={'effect_cues':[m.EffectCue(kind=kind,at=at)]})
        render_effects(isolated/(kind+'.wav'),4,plan_effects(custom,{},None,5),5)
        assert (isolated/(kind+'.wav')).stat().st_size>1000


def test_director_failure_preserves_export_fallback_and_off_never_calls_ai(monkeypatch):
    monkeypatch.setattr('backend.sound_design.directed_events',lambda *args:(_ for _ in ()).throw(ValueError('fixture offline')))
    monkeypatch.setattr('backend.sound_design.motion_moment',lambda *args:None)
    clip=m.Clip(id='a'*32,title='Moment',voiceover='',duration=4)
    plan=plan_effects(clip,{},None,5)
    assert not plan['events'] and plan.get('notice')
    clip.effects_mode='off';assert not plan_effects(clip,{},None,5).get('notice')
