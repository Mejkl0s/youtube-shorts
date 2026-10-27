import shutil
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import main as m
from backend import free_search as f
from backend.clip_editor import recut_all
from backend.rank_notes import NOTE_BANK, fresh_notes
from backend.scene_context import reframe_regions
from test_workflow import isolated


def late_point(path,duration=12):
    m.ffmpeg('-f','lavfi','-i',f'color=c=gray:s=320x180:r=15:d={duration}',
             '-f','lavfi','-i',f'sine=frequency=440:sample_rate=44100:duration={duration}',
             '-vf',"drawbox=x=0:y=40:w=30:h=60:color=lime:t=fill:enable='gte(t,10.5)'",
             '-c:v','libx264','-c:a','aac',str(path))


def test_free_selection_preserves_setup_and_late_ending(isolated):
    folder=isolated/'media'/uuid.uuid4().hex
    folder.mkdir()
    late_point(folder/'input.mp4')
    (folder/'input.mp4').rename(folder/'source')
    source=m.register(folder/'source',folder.name,'Late ending')
    selected=f.select_free([source],'winter fails',require_five=False)
    assert len(selected)==1
    assert selected[0]['start']==0 and selected[0]['duration']>=11.9
    assert selected[0]['framing']=='fit' and selected[0]['has_audio']


def test_long_shot_uses_motion_peak_with_leadup_and_aftermath(isolated):
    path=isolated/'long.mp4'
    m.ffmpeg('-f','lavfi','-i','color=c=gray:s=160x90:r=2:d=90','-vf',
             "drawbox=x=20:y=20:w=18:h=18:color=white:t=fill:enable='between(t,55,57)'",'-c:v','libx264',str(path))
    windows=m.scene_windows(path)
    assert len(windows)==1
    start,length=windows[0]
    assert length==30 and start<=50 and start+length>=61
    assert windows[0].scene_start==0 and windows[0].scene_end==90


def test_batch_recovers_original_ending_full_frame_and_sound_in_real_mp4(isolated):
    source_file=isolated/'input.mp4'
    late_point(source_file)
    old=[]
    for _ in range(5):
        folder=isolated/'media'/uuid.uuid4().hex
        folder.mkdir()
        shutil.copyfile(source_file,folder/'source')
        source=m.register(folder/'source',folder.name,'Late ending')
        cut=m.materialize_scenes([{**source,'title':'Moment','voiceover':'','rank_note':'Keep this note',
                                  'start':2,'duration':4,'sourceDuration':12,'scene_start':0,'scene_end':12,'_cut_scene':True}])[0]
        old.append({**cut,'framing':'fill','rank_note':'Keep this note'})
    job=uuid.uuid4().hex
    m.jobs[job]={'id':job}
    recut_all(job,old)
    assert m.jobs[job]['status']=='done',m.jobs[job]
    clips=m.jobs[job]['clips']
    assert len({c['id'] for c in clips})==5
    assert all(c['duration']>=11.9 and c['start']==0 and c['source_start']==0 for c in clips)
    assert all(c['has_audio'] and c['framing']=='fit' and c['rank_note']=='Keep this note' for c in clips)
    assert all((isolated/'media'/c['id']/'source').exists() for c in old)
    render=uuid.uuid4().hex
    m.jobs[render]={'id':render}
    project=m.Project(title='WINTER FAILS',clips=clips,voice=False,effects=False,resolution='720')
    assert project.original_volume==.8
    m.render(render,project)
    assert m.jobs[render]['status']=='done',m.jobs[render]
    output=isolated/'jobs'/render/'ranking.mp4'
    # The late event at the LEFT EDGE survives timing AND portrait framing.
    raw=m.ffmpeg('-ss','11.2','-i',str(output),'-frames:v','1','-vf','crop=4:4:12:548,format=rgb24','-f','rawvideo','pipe:1')
    pixel=np.frombuffer(raw,np.uint8).reshape(-1,3).mean(axis=0)
    assert pixel[1]>180 and pixel[0]<80 and pixel[2]<80,pixel
    audio=m.ffmpeg('-i',str(output),'-t','1','-vn','-ac','1','-f','s16le','pipe:1')
    assert np.abs(np.frombuffer(audio,dtype='<i2').astype(float)).mean()>1000


def test_context_edit_validates_bounds_and_keeps_original(isolated):
    folder=isolated/'media'/uuid.uuid4().hex
    folder.mkdir()
    late_point(folder/'test.mp4')
    (folder/'test.mp4').rename(folder/'source')
    source=m.register(folder/'source',folder.name,'Context')
    client=TestClient(m.app)
    base={'id':source['id'],'start':0,'duration':4}
    ctx=client.post('/api/clip-context',json=base)
    assert ctx.status_code==200 and ctx.json()['bounds']['end']>=12
    assert client.post('/api/clip-cut',json={**base,'cut_start':0,'cut_end':35}).status_code==400
    assert client.post('/api/clip-cut',json={**base,'cut_start':0,'cut_end':'NaN'}).status_code==422
    cut=client.post('/api/clip-cut',json={**base,'cut_start':0,'cut_end':12,'framing':'fit'})
    assert cut.status_code==200,cut.text
    assert cut.json()['sourceDuration']>=11.9 and cut.json()['has_audio']
    assert (folder/'source').is_file()
    # A camera cut may have split one action; explicit full-source review can
    # extend beyond the detector's boundary without losing the original file.
    bounded=m.materialize_scenes([{**source,'title':'Moment','voiceover':'','start':2,'duration':4,
                                  'sourceDuration':12,'scene_start':2,'scene_end':6,'_cut_scene':True}])[0]
    request={'id':bounded['id'],'start':0,'duration':4,'cut_start':8,'cut_end':12}
    assert client.post('/api/clip-cut',json=request).status_code==400
    expanded=client.post('/api/clip-cut',json={**request,'full_source':True})
    assert expanded.status_code==200,expanded.text
    assert expanded.json()['source_start']==8
    assert client.post('/api/clip-context',json={'id':'../private'}).status_code==404


def test_reframing_keeps_blur_on_same_source_pixels():
    mask={'x':.1,'y':.4,'w':.2,'h':.1,'origin':'manual'}
    fitted=reframe_regions([mask],1920,1080,'fill','fit')
    assert len(fitted)==1
    restored=reframe_regions(fitted,1920,1080,'fit','fill')
    for key in ('x','y','w','h'):
        assert abs(restored[0][key]-mask[key])<.00001


def test_notes_change_between_selections_without_repeats(isolated):
    first=fresh_notes(5,'en')
    for _ in range(20):fresh_notes(1,'en')  # intervening candidate downloads
    second=fresh_notes(5,'en')
    assert len(set(first))==len(set(second))==5 and not set(first)&set(second)
    assert all(m.word_count(text)<=4 and len(text)<=40 for bank in NOTE_BANK.values() for text in bank)
    client=TestClient(m.app)
    response=client.post('/api/rank-notes',json={'language':'cs','exclude':first})
    assert response.status_code==200 and len(set(response.json()['notes']))==5

