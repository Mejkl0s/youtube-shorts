import wave
import uuid

import numpy as np
import pytest

from backend import main as m
from backend.speech_fit import speech_bounds, trim_speech, placement
from test_workflow import isolated, make_source


def padded_voice(path, seconds=.8, lead=.6, tail=1.2):
    rate=24000
    tone=(np.sin(2*np.pi*440*np.arange(round(rate*seconds))/rate)*6000).astype('<i2')
    samples=np.concatenate([np.zeros(round(rate*lead),dtype='<i2'),tone,np.zeros(round(rate*tail),dtype='<i2')])
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(samples.tobytes())
    return samples


def test_removes_only_boundary_silence_and_keeps_complete_words_and_internal_pauses(tmp_path):
    path=tmp_path/'speech.wav';samples=padded_voice(path)
    first,last=speech_bounds(samples,24000)
    assert abs(first/24000-.52)<.02 and abs(last/24000-1.5)<.02
    duration=trim_speech(path)
    assert .96<duration<1.01
    with wave.open(str(path),'rb') as audio:clean=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2')
    assert np.array_equal(clean,samples[first:last])
    samples[round(.9*24000):round(1.1*24000)]=0
    assert speech_bounds(samples,24000)==(first,last)
    with pytest.raises(ValueError,match='ticho'):speech_bounds(np.zeros(24000,dtype='<i2'),24000)


@pytest.mark.parametrize('clip_seconds',[1,1.2,1.99,2,2.01,4.1])
def test_fit_reduces_leadin_before_rejecting_voice_and_never_cuts_words(clip_seconds):
    speech=(clip_seconds-.12)*1.2
    timing=placement(speech,clip_seconds)
    assert timing is not None
    speed,delay=timing
    assert 1<=speed<=1.25
    assert delay/1000+speech/speed<=clip_seconds-.05
    assert placement(clip_seconds*1.5,clip_seconds) is None
    natural=placement(1.7,2)
    assert natural[0]==1 and 170<=natural[1]<=180


@pytest.mark.parametrize('language',['en','cs'])
def test_real_mp4_fits_padded_announcements_and_short_rank_fallback_with_effects(isolated,monkeypatch,language):
    clips=[];calls=[]
    durations=[4.1,1,2,1.2,2]
    for duration in durations:
        meta=make_source(isolated/'media'/uuid.uuid4().hex,'blue',duration=5)
        # #4 also represents an older saved announcement without its rank flag.
        legacy=len(clips)==1
        clips.append({**meta,'title':'Short event','voiceover':m.rank_lines(language)[1] if legacy else '',
                      'narration_mode':'custom' if legacy else 'rank','duration':duration,'effects_mode':'manual','effect_at':.65})
    def speech(text,language,path,config=None):
        calls.append(text)
        padded_voice(path,seconds=1.5 if text in ('Number four.','Čtvrté místo.') else .45 if text in ('Four.','Čtvrté.') else .85)
    monkeypatch.setattr(m,'synthesize',speech)
    project=m.Project(title='SHORT RANKING',clips=clips,voice=True,effects=True,resolution='720',language=language)
    job=uuid.uuid4().hex;m.jobs[job]={'id':job};m.render(job,project)
    assert m.jobs[job]['status']=='done',m.jobs[job]
    compact='Four.' if language=='en' else 'Čtvrté.'
    assert len(m.jobs[job]['warnings'])==1 and compact in m.jobs[job]['warnings'][0]
    expected=m.rank_lines(language);expected.insert(2,compact)
    assert calls==expected
    assert [c.voiceover for c in project.clips]==m.rank_lines(language)
    path=isolated/'jobs'/job/'ranking.mp4'
    assert abs(float(m.probe(path)['format']['duration'])-sum(durations))<.08
    raw=m.ffmpeg('-i',str(path),'-vn','-ac','1','-ar','24000','-f','s16le','pipe:1')
    samples=np.frombuffer(raw,dtype='<i2').astype(float)
    offset=0
    for duration in durations:
        beginning=samples[round((offset+.02)*24000):round((offset+.12)*24000)]
        voice=samples[round((offset+.5)*24000):round((offset+.7)*24000)]
        assert np.abs(beginning).mean()<10  # No arbitrary effect at the cut boundary.
        assert m.jobs[job]['effects_plan'][durations.index(duration)]['events']
        assert np.abs(voice).mean()>300  # Complete voiced line, not just SFX.
        offset+=duration


def test_custom_sentence_is_not_silently_rewritten_or_cut(isolated,monkeypatch):
    clips=[];calls=[]
    for _ in range(5):
        meta=make_source(isolated/'media'/uuid.uuid4().hex,'blue',duration=2)
        clips.append({**meta,'title':'Event','voiceover':'Keep every word.','duration':1})
    def speech(text,language,path,config=None):
        calls.append(text);padded_voice(path,seconds=2)
    monkeypatch.setattr(m,'synthesize',speech)
    project=m.Project(title='CUSTOM',clips=clips,voice=True,effects=True,resolution='720')
    job=uuid.uuid4().hex;m.jobs[job]={'id':job};m.render(job,project)
    assert m.jobs[job]['status']=='failed'
    assert 'Zkrať jeho text' in m.jobs[job]['message']
    assert calls==['Keep every word.']
    assert project.clips[0].duration==1 and project.clips[0].voiceover=='Keep every word.'
