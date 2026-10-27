import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main as m
from backend import free_search as f
from backend.cleanup import BlurRegion, blur_filters, detect_text
from test_workflow import isolated, make_source


def compilation(folder):
    folder.mkdir()
    colors = ['red', 'blue', 'yellow', 'purple', 'cyan']
    inputs = [arg for color in colors for arg in ('-f', 'lavfi', '-i', f'color=c={color}:s=160x284:r=24:d=3')]
    m.ffmpeg(*inputs, '-filter_complex', ''.join(f'[{i}:v]' for i in range(5))+'concat=n=5:v=1:a=0[v]',
             '-map', '[v]', '-c:v', 'libx264', '-f', 'mp4', str(folder/'source'))
    return m.register(folder/'source', folder.name, 'Winter fails compilation')


def pixels(path, at=1, vf='scale=90:160,format=rgb24', shape=(160,90,3)):
    return np.frombuffer(m.ffmpeg('-ss', str(at), '-i', str(path), '-frames:v', '1', '-vf', vf, '-f', 'rawvideo', 'pipe:1'), np.uint8).reshape(shape)


def test_one_compilation_produces_five_real_independent_cuts_and_exports(isolated):
    parent = compilation(isolated/'media'/uuid.uuid4().hex)
    windows = m.scene_windows(isolated/'media'/parent['id']/'source')
    assert len({window.shot for window in windows}) == 5
    body = m.CompilationRequest(id=parent['id'], blur_text=False)
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id':job_id}
    m.split_compilation(job_id, body)
    job = m.jobs[job_id]
    assert job['status'] == 'done', job
    clips = job['clips']
    assert len({c['id'] for c in clips}) == 5
    assert parent['id'] not in {c['id'] for c in clips}
    assert len({round(c['source_start']/3) for c in clips}) == 5
    expected = [(255,0,0),(0,0,255),(255,255,0),(128,0,128),(0,255,255)]
    for clip in clips:
        assert clip['start'] == 0 and abs(clip['sourceDuration']-3)<.05
        path = isolated/'media'/clip['id']/'source'
        index = round(clip['source_start']/3)
        for at in (.1,2.85):
            assert np.abs(pixels(path,at).astype(float).mean(axis=(0,1))-expected[index]).max()<10
    project = m.Project(title='WINTER FAILS',clips=clips,voice=False,effects=False,resolution='720')
    render_id = uuid.uuid4().hex
    m.jobs[render_id] = {'id':render_id}
    m.render(render_id,project)
    assert m.jobs[render_id]['status']=='done',m.jobs[render_id]
    assert abs(float(m.probe(isolated/'jobs'/render_id/'ranking.mp4')['format']['duration'])-15)<.15


def test_long_single_shot_is_never_reused_to_fill_five(isolated):
    candidate = make_source(isolated/'media'/uuid.uuid4().hex,'red',duration=12)
    assert len(m.scene_windows(isolated/'media'/candidate['id']/'source')) == 1
    partial = f.select_free([candidate],'winter fails',require_five=False)
    assert len(partial)==1
    with pytest.raises(ValueError,match='Pouze 1'):
        f.select_free([candidate],'winter fails')


def test_compilation_past_old_two_minute_limit_has_complete_preview_and_tail_cut(isolated):
    folder=isolated/'media'/uuid.uuid4().hex
    folder.mkdir()
    m.ffmpeg('-f','lavfi','-i','color=c=red:s=160x284:r=1:d=125',
             '-f','lavfi','-i','color=c=blue:s=160x284:r=1:d=5',
             '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]',
             '-map','[v]','-c:v','libx264','-f','mp4',str(folder/'source'))
    candidate=m.register(folder/'source',folder.name,'Long compilation')
    assert abs(float(m.probe(folder/'preview.mp4')['format']['duration'])-130)<.1
    clips=f.select_free([candidate],'winter fails',require_five=False)
    assert len(clips)==2
    tail=next(clip for clip in clips if clip['source_start']>=125)
    assert tail['start']==0 and abs(tail['sourceDuration']-5)<.05  # one encoded frame
    assert np.abs(pixels(isolated/'media'/tail['id']/'source').astype(float).mean(axis=(0,1))-[0,0,255]).max()<10


def test_ai_may_use_separate_shots_but_not_two_windows_of_same_shot(isolated,monkeypatch):
    candidate = compilation(isolated/'media'/uuid.uuid4().hex)
    selection={'clips':[{'scene':i,'title':f'Moment {i}','voiceover':'Better timing.','reason':'A test scene.'} for i in range(5)]}
    monkeypatch.setattr(m,'ai_request',lambda *args:selection)
    result=m.select_candidates([candidate],'winter fails','en')
    assert len({clip['id'] for clip in result})==5
    selection['clips'][1]['scene']=0
    with pytest.raises(ValueError,match='stejné video'):
        m.select_candidates([candidate],'winter fails','en')


@pytest.mark.parametrize('background,box',[('navy',''),('yellow','drawbox=x=40:y=260:w=640:h=150:color=black:t=fill,')])
def test_real_ocr_finds_burned_in_text_in_portrait_coordinates(isolated,background,box):
    source=isolated/'text.mp4'
    m.ffmpeg('-f','lavfi','-i',f'color=c={background}:s=720x1280:r=15:d=3','-vf',
             box+f"drawtext=fontfile={m.filter_path(m.FONTS['bold'])}:text='WINTER FAILS':fontsize=50:fontcolor=white:x=80:y=300",
             '-c:v','libx264',str(source))
    regions,note=detect_text(source,0,3)
    assert regions,note
    assert any(r['x']<.15 and r['y']<.25 and r['x']+r['w']>.65 and r['y']+r['h']>.26 for r in regions),regions
    assert all(r['origin']=='auto' for r in regions)
    assert sum(r['w']*r['h'] for r in regions)<=.35


def test_blur_is_local_and_rendered_own_title_remains_sharp(isolated):
    clips=[]
    for _ in range(5):
        folder=isolated/'media'/uuid.uuid4().hex
        folder.mkdir()
        m.ffmpeg('-f','lavfi','-i','color=c=navy:s=180x320:r=15:d=2','-vf',
                 "drawgrid=w=8:h=8:t=2:c=white",'-c:v','libx264','-f','mp4',str(folder/'source'))
        meta=m.register(folder/'source',folder.name,'Grid')
        clips.append({**meta,'title':'Grid','voiceover':'','start':0,'duration':2,
                      'blur_regions':[{'x':.1,'y':.02,'w':.8,'h':.95}]})
    project=m.Project(title='MY WINTER FAILS',clips=clips,voice=False,effects=False,captions=False,resolution='720',
                      layout=m.Layout(header_darkness=0,title_style='plain',rank_style='plain',show_label=False,show_criteria=False))
    job_id=uuid.uuid4().hex
    m.jobs[job_id]={'id':job_id}
    m.render(job_id,project)
    assert m.jobs[job_id]['status']=='done',m.jobs[job_id]
    output=isolated/'jobs'/job_id/'ranking.mp4'
    original=pixels(isolated/'media'/clips[0]['id']/'source',vf='scale=720:1280,format=rgb24',shape=(1280,720,3))
    rendered=pixels(output,vf='format=rgb24',shape=(1280,720,3))
    # Blur removes grid contrast inside the region; edges outside retain contrast.
    assert rendered[800:1000,200:500].std() < original[800:1000,200:500].std()*.65
    assert rendered[800:1000,:50].std() > rendered[800:1000,200:500].std()*1.3
    # The editor's own title is drawn after blur: white letters have sharp edges.
    title=rendered[20:180,72:648].astype(float)
    assert (np.max(np.abs(np.diff(title,axis=1)),axis=2)>90).sum()>150
    # Medal number remains gold despite overlapping a broad source mask.
    gold=(np.abs(rendered.astype(int)-[255,211,78]).max(axis=2)<25)
    assert gold.sum()>100


@pytest.mark.parametrize('region',[
    {'x':.9,'y':0,'w':.5,'h':.1}, {'x':0,'y':0,'w':0,'h':.1},
    {'x':float('nan'),'y':0,'w':.1,'h':.1}, {'x':0,'y':0,'w':.1,'h':.1,'origin':'filter;inject'},
])
def test_invalid_blur_coordinates_are_rejected(region):
    with pytest.raises(ValidationError):BlurRegion(**region)


def test_cleanup_endpoint_validates_asset_and_bounds_and_manual_works_without_ocr(isolated,monkeypatch):
    meta=make_source(isolated/'media'/uuid.uuid4().hex)
    client=TestClient(m.app)
    assert client.post('/api/blur-suggestions',json={'id':'../private'}).status_code==404
    assert client.post('/api/blur-suggestions',json={'id':meta['id'],'start':2,'duration':4}).status_code==400
    monkeypatch.setattr('backend.cleanup.shutil.which',lambda _:None)
    response=client.post('/api/blur-suggestions',json={'id':meta['id'],'duration':2})
    assert response.status_code==200 and response.json()['regions']==[]
    filters,_=blur_filters([BlurRegion(x=.1,y=.2,w=.3,h=.1)],720,1280)
    assert 'gblur' in ';'.join(filters)


def test_full_heading_search_keeps_topic_and_accepts_watch_compilations(monkeypatch):
    queries=[]
    def engine(query,provider):
        queries.append(query)
        return [{'url':'https://www.youtube.com/watch?v=WINTER00001','title':'Funny winter fails compilation'},
                {'url':'https://www.youtube.com/watch?v=VIVALDI0001','title':'Antonio Vivaldi Winter'}]
    monkeypatch.setattr(f,'engine_results',engine)
    results,_=f.public_search('ranking funniest winter fails',True,8)
    assert len(results)==1 and results[0]['url'].endswith('WINTER00001')
    assert all('ranking' not in query and 'funny winter fails' in query for query in queries)
    assert any(query.endswith('site:youtube.com') for query in queries)
