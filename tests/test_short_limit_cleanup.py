import uuid
import time

import numpy as np
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main as m
from backend import cleanup as c
from backend.timeline import choose_moments
from test_workflow import isolated


def project_rows(durations):
    return [{'id':uuid.uuid4().hex,'title':'Moment','voiceover':'','duration':d,'start':0} for d in durations]


@pytest.mark.parametrize('durations',[(1,1.5,2,1.5,2),(5,6,7,9,10),(8,8,8,8,8)])
def test_total_ceiling_accepts_eight_thirty_seven_and_forty_seconds(durations):
    project=m.Project(title='Ranking',clips=project_rows(durations),voice=False)
    assert sum(c.duration for c in project.clips)==sum(durations)
    assert len(project.clips)==5


def test_total_limit_rejects_long_saved_project_before_queue(isolated):
    rows=project_rows([8.1]*5)
    with pytest.raises(ValidationError,match='40 sekund'):m.Project(title='Ranking',clips=rows,voice=False)
    result=TestClient(m.app).post('/api/render',json={'title':'Ranking','clips':rows,'voice':False})
    assert result.status_code==422 and not m.jobs


def test_selection_chooses_whole_shorter_alternatives_instead_of_truncating():
    rows=[{'id':i,'duration':d,'score':score} for i,(d,score) in enumerate([(20,1),(15,.9),(12,.8),(8,.7),(7,.6),(6,.5),(5,.4),(4,.3)])]
    chosen=choose_moments(rows,duration=lambda r:r['duration'],score=lambda r:r['score'],identity=lambda r:r['id'],source=lambda r:r['id'])
    assert len(chosen)==5 and sum(r['duration'] for r in chosen)<=40
    assert all(row==rows[row['id']] for row in chosen)
    assert choose_moments(rows[:5],duration=lambda r:r['duration'],score=lambda r:r['score'],identity=lambda r:r['id'],source=lambda r:r['id'])==[]


def test_fractional_complete_moments_can_fill_forty_without_rounding_rejection():
    rows=[{'id':i,'duration':d} for i,d in enumerate((7.99,7.99,7.99,7.99,8.04))]
    result=choose_moments(rows,duration=lambda r:r['duration'],score=lambda r:1,identity=lambda r:r['id'],source=lambda r:r['id'])
    assert len(result)==5 and sum(row['duration'] for row in result)<=40.0000001


@pytest.mark.parametrize('durations',[(1,1.5,2,1.5,2),(5,6,7,9,10),(8,8,8,8,8)])
def test_actual_mp4_respects_ceiling_and_never_pads_to_forty(isolated,durations):
    clips=[]
    for d in durations:
        identity=uuid.uuid4().hex;folder=isolated/'media'/identity;folder.mkdir()
        m.ffmpeg('-f','lavfi','-i',f'color=c=navy:s=160x284:r=30:d={d}',
                 '-f','lavfi','-i',f'sine=frequency=440:duration={d}',
                 '-c:v','libx264','-c:a','aac','-f','mp4',str(folder/'source'))
        meta=m.register(folder/'source',identity,'Moment',fast_preview=True)
        clips.append({**meta,'title':'Moment','voiceover':'','start':0,'duration':d})
    project=m.Project(title='Ranking',clips=clips,voice=False,effects=False,resolution='720')
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity}
    m.render(identity,project)
    assert m.jobs[identity]['status']=='done',m.jobs[identity]
    meta=m.probe(isolated/'jobs'/identity/'ranking.mp4')
    assert abs(float(meta['format']['duration'])-sum(durations))<.04
    assert float(meta['format']['duration'])<=40
    assert next(s for s in meta['streams'] if s['codec_type']=='video')['nb_frames']==str(round(sum(durations)*30))


def test_black_graphics_are_detected_but_letterbox_padding_is_not():
    image=Image.new('RGB',(720,1280),'navy')
    draw=ImageDraw.Draw(image);draw.rectangle((100,250,400,390),fill='black')
    boxes=c.black_blocks(image,(0,0,1,1))
    assert len(boxes)==1 and boxes[0]['method']=='remove'
    padded=Image.new('RGB',(720,1280),'black');ImageDraw.Draw(padded).rectangle((0,400,719,879),fill='navy')
    assert c.black_blocks(padded,(0,400/1280,1,880/1280))==[]


def test_cleanup_keeps_black_detection_without_ocr_and_does_not_mark_motion(isolated,monkeypatch):
    source=isolated/'block.mp4'
    m.ffmpeg('-f','lavfi','-i','color=c=navy:s=360x640:r=15:d=1',
             '-vf',"drawbox=x=60:y=150:w=170:h=80:color=black:t=fill",'-c:v','libx264',str(source))
    monkeypatch.setattr(c.shutil,'which',lambda _:None)
    monkeypatch.setattr(c,'vision_regions',lambda *args:([],False))
    regions,_=c.detect_text(source,0,1,'fit')
    assert regions and any(r['kind']=='block' and r['method']=='remove' for r in regions)


def test_local_logo_coordinates_are_validated_and_own_padding_ignored(monkeypatch):
    from backend import local_vision
    monkeypatch.setattr(local_vision,'status',lambda:{'ready':True})
    monkeypatch.setattr(local_vision,'request',lambda *args:{'regions':[
        {'x':.8,'y':.3,'w':.1,'h':.06,'kind':'logo','method':'remove','confidence':.98,'seen_frames':3},
        {'x':0,'y':0,'w':1,'h':.9,'kind':'block','method':'remove','confidence':1,'seen_frames':3},
        {'x':.2,'y':.05,'w':.2,'h':.1,'kind':'text','method':'blur','confidence':.99,'seen_frames':3},
        {'x':.2,'y':.5,'w':.2,'h':.1,'kind':'logo','method':'blur','confidence':.2,'seen_frames':3}]})
    result,used=c.vision_regions([Image.new('RGB',(720,1280))]*3,(0,.25,1,.75))
    assert used and len(result)==1 and result[0]['method']=='blur' and result[0]['kind']=='logo'


def test_remove_interpolates_black_block_and_own_overlays_remain_sharp(isolated):
    clips=[]
    for _ in range(5):
        identity=uuid.uuid4().hex;folder=isolated/'media'/identity;folder.mkdir()
        m.ffmpeg('-f','lavfi','-i','color=c=blue:s=180x320:r=30:d=1.6',
                 '-vf','drawbox=x=40:y=120:w=80:h=50:color=black:t=fill','-c:v','libx264','-f','mp4',str(folder/'source'))
        meta=m.register(folder/'source',identity,'Blocked',fast_preview=True)
        clips.append({**meta,'title':'Moment','voiceover':'','start':0,'duration':1.6,
                      'blur_regions':[{'x':.2,'y':.35,'w':.5,'h':.21,'method':'remove'}]})
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity}
    m.render(identity,m.Project(title='MY TITLE',clips=clips,voice=False,effects=False,captions=False,resolution='720'))
    assert m.jobs[identity]['status']=='done',m.jobs[identity]
    out=isolated/'jobs'/identity/'ranking.mp4'
    raw=m.ffmpeg('-ss','0.8','-i',str(out),'-frames:v','1','-vf','format=rgb24','-f','rawvideo','pipe:1')
    pixels=np.frombuffer(raw,np.uint8).reshape(1280,720,3)
    assert pixels[560,320,2]>200 and pixels[560,320,0]<35
    # The editor draws its title and medal ranks AFTER interpolating the source.
    title=pixels[20:200].astype(float)
    assert (np.max(abs(np.diff(title,axis=1)),axis=2)>90).sum()>100


def test_cleaning_existing_good_clips_preserves_selection_timing_and_manual_masks(isolated,monkeypatch):
    from test_workflow import make_source
    rows=[]
    manual={'x':.1,'y':.4,'w':.1,'h':.1,'origin':'manual','method':'remove'}
    detected={'x':.7,'y':.2,'w':.1,'h':.1,'origin':'auto','method':'blur','kind':'logo'}
    stale={'x':.2,'y':.6,'w':.1,'h':.1,'origin':'auto'}
    for i in range(5):
        meta=make_source(isolated/'media'/uuid.uuid4().hex,duration=3)
        rows.append({**meta,'title':f'Keep {i}','rank_note':f'Note {i}','voiceover':'Keep this line.',
                     'start':.5,'duration':2,'sourceDuration':3,'blur_regions':[manual,stale]})
    monkeypatch.setattr(m,'detect_text',lambda *args:([detected],'Fixture detection'))
    client=TestClient(m.app)
    response=client.post('/api/cleanup-clips',json={'clips':rows})
    assert response.status_code==202,response.text
    identity=response.json()['id'];deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        job=client.get('/api/jobs/'+identity).json()
        if job['status'] in ('done','failed'):break
        time.sleep(.02)
    assert job['status']=='done',job
    for old,new in zip(rows,job['clips']):
        for key in ('id','title','rank_note','voiceover','start','duration','sourceDuration'):
            assert old[key]==new[key]
        assert len(new['blur_regions'])==2
        assert new['blur_regions'][0]['origin']=='manual' and new['blur_regions'][0]['method']=='remove'
        assert new['blur_regions'][1]==detected
    assert client.post('/api/cleanup-clips',json={'clips':[rows[0]]*5}).status_code==422
