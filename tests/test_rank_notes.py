import uuid

import numpy as np
import pytest
from pydantic import ValidationError

from backend import main as m
from backend.rank_notes import note_geometry, describe_clips
from test_workflow import isolated, make_source


def test_notes_are_short_independent_of_speech_and_follow_the_clip():
    clips=[m.Clip(id=f'{i:032x}',title='Long source title',voiceover='Number five.',duration=2) for i in range(5)]
    project=m.Project(title='Winter fails',clips=clips,voice=False)
    assert all(c.rank_note=='' for c in project.clips)
    project.clips[0].rank_note='Ice wins!'
    swapped=list(reversed(project.clips))
    restored=m.Project(title=project.title,clips=swapped,voice=False)
    assert restored.clips[-1].rank_note=='Ice wins!'
    assert restored.clips[-1].voiceover=='Number five.'
    assert m.Clip(id='a'*32,title='x',voiceover='',rank_note='').rank_note==''
    for text in ['A note with five whole words', 'x'*41, 'first\nsecond']:
        with pytest.raises(ValidationError):m.Clip(id='a'*32,title='x',voiceover='',rank_note=text)


def test_real_export_notes_reveal_animate_and_remain_with_individual_number_colors(isolated):
    clips=[]
    for i in range(5):
        meta=make_source(isolated/'media'/uuid.uuid4().hex,'purple',duration=2)
        clips.append({**meta,'title':'SOURCE TITLE','voiceover':'Unwanted bottom narration.','duration':2,
                      'rank_note':['Skater falls backward','Ice gives way','Sled hits snow','Snowboard snaps','Skier lands sideways'][i]})
    layout=m.Layout(rank_palette='individual',rank_colors={1:'00FF00',2:'FF0000',3:'00FFFF',4:'FFFF00',5:'FFFFFF'},header_darkness=0)
    project=m.Project(title='WINTER FAILS',clips=clips,voice=False,effects=False,resolution='720',layout=layout)
    job=uuid.uuid4().hex;m.jobs[job]={'id':job};m.render(job,project)
    assert m.jobs[job]['status']=='done',m.jobs[job]
    path=isolated/'jobs'/job/'ranking.mp4'
    def frame(at):
        raw=m.ffmpeg('-ss',str(at),'-i',str(path),'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1')
        return np.frombuffer(raw,np.uint8).reshape(1280,720,3).astype(int)
    initial,entering,first,last=map(frame,(0,.25,1,9))
    assert np.abs(first[1000:-8]-[128,0,128]).max()<12
    for marker in layout.rank_markers(5):
        text=project.clips[5-marker['rank']].rank_note
        x,y,size=note_geometry(text,m.FONTS[layout.font],marker,720,1280,layout.rank_x)
        def whites(im):return (im[y:y+size+8,x:680].min(axis=2)>180).sum()
        assert whites(last)>20,marker  # All five notes remain by the last clip.
        if marker['rank']==5:
            assert whites(initial)<5
            assert whites(first)>20
            assert np.abs(entering[y:y+size+8,x:680]-first[y:y+size+8,x:680]).mean()>1
        else:
            assert whites(first)<5  # No notes for clips that have not played.
    green=(first[:,:,1]>180)&(first[:,:,0]<100)&(first[:,:,2]<100)
    assert green.sum()>100  # #1's individual color is already visible.


def test_notes_inspect_each_actual_cut_and_reject_generic_fallback(isolated,monkeypatch):
    clips=[]
    for i in range(2):
        meta=make_source(isolated/'media'/uuid.uuid4().hex,'red',duration=3)
        clips.append(m.Clip(id=meta['id'],title='Untrusted wrong title',voiceover='',start=.5,duration=2))
    from backend import visual_selection as visual
    calls=[];real_frames=visual.frames
    def frames(path,start,end,count):
        calls.append((path,start,end));return real_frames(path,start,end,count)
    monkeypatch.setattr(visual,'frames',frames)
    notes=iter(['Skater loses balance','Sled hits snow'])
    def request(prompt,evidence,tokens):
        assert 'RANK NOTE REVIEW' in prompt and 'Untrusted wrong title' not in prompt
        assert any(row['type']=='image_url' for row in evidence)
        return {'visible':True,'note':next(notes)}
    monkeypatch.setattr(m.local_vision,'request',request)
    assert describe_clips(clips)==['Skater loses balance','Sled hits snow']
    assert [(a,b) for _,a,b in calls]==[(.5,2.5),(.5,2.5)]
    monkeypatch.setattr(m.local_vision,'request',lambda *args:{'visible':True,'note':'Wait for it'})
    with pytest.raises(ValueError,match='obecnou'):describe_clips(clips[:1])
    monkeypatch.setattr(m.local_vision,'request',lambda *args:{'visible':False,'note':''})
    with pytest.raises(ValueError,match='jasný'):describe_clips(clips[:1])


def test_individual_colors_validate_and_survive_saved_layout():
    layout=m.Layout(rank_palette='individual',rank_colors={'1':'#ff0088',5:'00aaff'})
    restored=m.Layout.model_validate_json(layout.model_dump_json())
    assert [row['color'] for row in restored.rank_markers(5)]==['FF0088','C5CBD3','CD965D','FFFFFF','00AAFF']
    assert restored.model_copy(update={'rank_display':'single'}).rank_markers(5)[0]['color']=='00AAFF'
    for value in ({0:'FFFFFF'},{6:'FFFFFF'},{1:'nonsense'}):
        with pytest.raises(ValueError):m.Layout(rank_colors=value)


def test_note_job_uses_current_cut_and_preserves_old_notes_on_bad_response(isolated,monkeypatch):
    from fastapi.testclient import TestClient
    meta=make_source(isolated/'media'/uuid.uuid4().hex,'blue',duration=3)
    clip={**meta,'title':'Blue fixture','voiceover':'','rank_note':'Keep my words','end_audio':'mute','start':.5,'duration':2}
    monkeypatch.setattr(m.local_vision,'require_ready',lambda:None)
    monkeypatch.setattr(m.executor,'submit',lambda fn,*args:fn(*args))
    monkeypatch.setattr(m.local_vision,'request',lambda *args:{'visible':True,'note':'Blue shape moves'})
    client=TestClient(m.app)
    response=client.post('/api/rank-notes',json={'clips':[clip]})
    assert response.status_code==202,response.text
    job=client.get('/api/jobs/'+response.json()['id']).json()
    result=job['clips'][0]
    assert job['status']=='done' and result['rank_note']=='Blue shape moves'
    assert result['start']==.5 and result['duration']==2 and result['rank_note_auto']
    assert result['end_audio']=='mute' and result['url']==meta['url']
    monkeypatch.setattr(m.local_vision,'request',lambda *args:{'visible':True,'note':'No way!'})
    response=client.post('/api/rank-notes',json={'clips':[clip]})
    job=client.get('/api/jobs/'+response.json()['id']).json()
    assert job['status']=='failed' and 'clips' not in job
    assert clip['rank_note']=='Keep my words'
