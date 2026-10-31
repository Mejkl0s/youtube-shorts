import base64
import copy
import io
import time
import uuid

import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend import main as m
from backend import visual_selection as v
from backend import work_budget as work
from backend.clip_editor import review_sources, visual_reselect, VisualReviewRequest
from test_workflow import isolated, make_source


def responses(durations):
    scout={'shortlist':[{'scene':i,'start':0,'end':d-.2} for i,d in enumerate(durations)]}
    review={'moments':[{'scene':i,'topic_match':True,'complete':True,'confidence':.9,'score':20+i*10,
                       'start':0,'end':d-.2,'setup':{'time':.5,'observation':'Visible preparation'},
                       'action':{'time':d-2,'observation':'The main action is visible'},
                       'outcome':{'time':d-.5,'observation':'The outcome is visible'},
                       'title':f'Event {i}','voiceover':'Late result appears.','rank_note':f'Late result {i}',
                       'reason':'Visible setup, action and outcome.'} for i,d in enumerate(durations)]}
    return scout,review


def fake_ai(monkeypatch,durations,edit=None):
    scout,review=responses(durations)
    if edit:edit(scout,review)
    calls=[]
    def remote(payload,**kwargs):
        calls.append(payload)
        return copy.deepcopy(scout if 'SCOUT PASS' in payload['messages'][0]['content'] else review)
    monkeypatch.setattr(m,'ai_request',remote)
    return calls


def candidates(isolated,durations=(8,9,10,11,12)):
    result=[]
    for index,duration in enumerate(durations):
        identity=uuid.uuid4().hex;folder=isolated/'media'/identity;folder.mkdir()
        m.ffmpeg('-f','lavfi','-i',f'color=c=gray:s=320x180:r=15:d={duration}',
                 '-f','lavfi','-i',f'sine=frequency=440:duration={duration}',
                 '-vf',f"drawbox=x=0:y=40:w=30:h=60:color=lime:t=fill:enable='gte(t,{duration-1})'",
                 '-c:v','libx264','-c:a','aac','-f','mp4',str(folder/'source'))
        meta=m.register(folder/'source',identity,'Winter fails '+str(index))
        result.append(meta)
    return result


def test_real_pts_and_contact_sheet_include_late_event(isolated):
    source=candidates(isolated,(12,))[0]
    samples=v.frames(isolated/'media'/source['id']/'source',5,12,15)
    assert samples[0][0]==5 and 11.8<samples[-1][0]<12
    assert all(a[0]<b[0] for a,b in zip(samples,samples[1:]))
    # The actual late green event is decoded, preserving the left image edge.
    pixel=np.asarray(samples[-1][1])[100,4]
    assert pixel[1]>150 and pixel[0]<70,pixel
    images=v.sheets(3,samples)
    assert len(images)==2
    data=base64.b64decode(images[0]['image_url']['url'].split(',')[1])
    assert Image.open(io.BytesIO(data)).size==(896,794)


def test_two_pass_review_keeps_late_results_audio_and_specific_notes(isolated,monkeypatch):
    durations=(8,9,10,11,12)
    sources=candidates(isolated,durations)
    calls=fake_ai(monkeypatch,durations)
    result=m.select_candidates(sources,'winter fails','en')
    assert len(calls)==2
    assert all(c['model']=='gpt-4.1' for c in calls)
    assert 'FINAL REVIEW' in calls[1]['messages'][0]['content']
    assert all(any(c['type']=='image_url' for c in p['messages'][1]['content']) for p in calls)
    assert len({c['id'] for c in result})==5
    assert len({round(c['duration'],1) for c in result})==5
    assert all(c['duration']>7 and c['framing']=='fit' and c['has_audio'] for c in result)
    assert all(c['selection_version']=='visual-event-v2' and c['review_required'] for c in result)
    before=[c['rank_note'] for c in result]
    assert before==[f'Late result {i}' for i in range(5)]
    m.assign_notes(result,'en')
    assert [c['rank_note'] for c in result]==before
    for source,clip,duration in zip(sources,result,durations):
        assert clip['source_asset_id']==source['id'] and clip['source_start']==0
        assert (isolated/'media'/source['id']/'source').is_file()
        assert m.asset(clip['id'])['visual_review']==clip['visual_review']
        assert m.Clip.model_validate(clip).visual_review['action']['time']==duration-2
        raw=m.ffmpeg('-ss',str(duration-.6),'-i',str(isolated/'media'/clip['id']/'source'),
                     '-frames:v','1','-vf','crop=2:2:4:60,format=rgb24','-f','rawvideo','pipe:1')
        pixel=np.frombuffer(raw,np.uint8).reshape(-1,3).mean(axis=0)
        assert pixel[1]>180 and pixel[0]<70


@pytest.fixture
def lightweight(monkeypatch):
    sources=[{'id':uuid.uuid4().hex,'name':'Unverified title','duration':12} for _ in range(6)]
    monkeypatch.setattr(m,'scene_windows',lambda path:[m.SceneWindow(0,12,0,0,12)])
    monkeypatch.setattr(v,'frames',lambda path,start,end,count:[(start,Image.new('RGB',(224,224))),(end-.05,Image.new('RGB',(224,224)))])
    monkeypatch.setattr(m,'materialize_scenes',lambda clips:clips)
    return sources


@pytest.mark.parametrize('change',[
    lambda s,r:r['moments'][0].update(complete=False),
    lambda s,r:r['moments'][0].update(topic_match=False),
    lambda s,r:r['moments'][0].update(confidence=.6),
])
def test_incomplete_unrelated_uncertain_events_do_not_fill_five(lightweight,monkeypatch,change):
    fake_ai(monkeypatch,[12]*5,change)
    with pytest.raises(v.VisualSelectionError,match='4/5'):
        m.select_candidates(lightweight[:5],'winter fails','en')


@pytest.mark.parametrize('change',[
    lambda s,r:r['moments'][0].update(end=7),  # before the outcome
    lambda s,r:r['moments'][0]['outcome'].update(time=13),
    lambda s,r:r['moments'][0]['action'].update(time=float('nan')),
    lambda s,r:r['moments'][0].pop('outcome'),
    lambda s,r:r['moments'][0].update(start=True),
    lambda s,r:r['moments'][0].update(end=30),
    lambda s,r:r['moments'][0].update(scene=99),
    lambda s,r:r['moments'][1].update(scene=0),
    lambda s,r:s['shortlist'][0].update(start=-1),
    lambda s,r:s['shortlist'][0].update(end=40),
])
def test_rejects_unsupported_timestamps_missing_evidence_and_repeated_shots(lightweight,monkeypatch,change):
    fake_ai(monkeypatch,[12]*5,change)
    with pytest.raises(ValueError):m.select_candidates(lightweight[:5],'winter fails','en')


def test_ranks_by_visible_event_score_and_rejects_sixth_unrelated_video(lightweight,monkeypatch):
    def edit(s,r):
        for item,score in zip(r['moments'],(30,80,60,20,90,100)):
            item['score']=score
        r['moments'][-1]['topic_match']=False
    fake_ai(monkeypatch,[12]*6,edit)
    selected=m.select_candidates(lightweight,'winter fails','en')
    assert [c['visual_review']['score'] for c in selected]==[20,30,60,80,90]
    assert lightweight[5]['id'] not in {c['id'] for c in selected}


def test_missing_key_is_explicit_and_never_calls_paid_service(isolated,monkeypatch):
    monkeypatch.setattr(m,'ai_request',lambda *args:pytest.fail('Paid service called without integration'))
    client=TestClient(m.app)
    assert client.post('/api/visual-reselect',json={'clips':[{'id':'a'*32}],'topic':'winter fails'}).status_code==409
    assert client.post('/api/compilation',json={'id':'a'*32,'mode':'ai'}).status_code==409


def test_failed_visual_discovery_never_substitutes_technical_selection(isolated,monkeypatch):
    rows=[{'url':f'https://www.tiktok.com/@winter/video/{100000+i}','title':'Winter fails'} for i in range(6)]
    monkeypatch.setattr(m,'public_search',lambda *args:(rows,[]))
    monkeypatch.setattr(m,'download_candidate',lambda item:{'id':uuid.uuid4().hex,'name':'Winter fails','duration':12})
    monkeypatch.setattr(m,'select_candidates',lambda *args:(_ for _ in ()).throw(v.VisualSelectionError('Missing visible outcome')))
    monkeypatch.setattr(m,'select_free',lambda *args,**kw:pytest.fail('Unreviewed fallback masquerading as AI'))
    job=uuid.uuid4().hex;m.jobs[job]={'id':job}
    m.discover(job,m.DiscoverRequest(topic='winter fails',mode='ai',allow_youtube=False,blur_text=False))
    assert m.jobs[job]['status']=='failed' and m.jobs[job]['partial_clips']==[]
    assert len(m.jobs[job]['downloaded_sources'])==6


def test_ai_service_failure_does_not_download_more_pools_or_retry_paid_review(isolated,monkeypatch):
    rows=[{'url':f'https://www.tiktok.com/@winter/video/{100000+i}','title':'Winter fails'} for i in range(24)]
    monkeypatch.setattr(m,'public_search',lambda *args:(rows,[]))
    downloads=[]
    def download(item):
        downloads.append(item)
        return {'id':uuid.uuid4().hex,'name':'Winter fails','duration':12}
    monkeypatch.setattr(m,'download_candidate',download)
    monkeypatch.setattr(m,'select_candidates',lambda *args:(_ for _ in ()).throw(ValueError('AI služba vrátila HTTP 401.')))
    monkeypatch.setattr(m,'youtube_search',lambda *args:pytest.fail('Provider failure caused more downloads'))
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity}
    m.discover(identity,m.DiscoverRequest(topic='winter fails',mode='ai',blur_text=False))
    assert m.jobs[identity]['status']=='failed' and '401' in m.jobs[identity]['message']
    assert len(downloads)==len(m.jobs[identity]['downloaded_sources'])==6


def test_existing_short_cut_is_reviewed_using_entire_retained_original(isolated,monkeypatch):
    sources=candidates(isolated,(12,))
    source=sources[0]
    cut=m.materialize_scenes([{**source,'title':'Old cut','voiceover':'','start':2,'duration':4,
                              'sourceDuration':12,'_cut_scene':True}])[0]
    assert review_sources([cut])[0]['id']==source['id']
    assert review_sources([cut])[0]['duration']==12
    old=m.asset(cut['id'])
    monkeypatch.setattr(m,'select_candidates',lambda *args:(_ for _ in ()).throw(v.VisualSelectionError('No complete event')))
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity}
    visual_reselect(identity,VisualReviewRequest(clips=[cut],topic='winter fails',blur_text=False))
    assert m.jobs[identity]['status']=='failed'
    assert 'Předchozí střihy' in m.jobs[identity]['message']
    assert m.asset(cut['id'])==old and (isolated/'media'/source['id']/'source').is_file()


def test_visual_reselect_success_via_real_async_endpoint(isolated,monkeypatch):
    sources=candidates(isolated)
    fake_ai(monkeypatch,(8,9,10,11,12))
    monkeypatch.setenv('OPENAI_API_KEY','fixture-not-a-real-key')
    rows=[{**s,'title':s['name'],'voiceover':'','start':0,'duration':4} for s in sources]
    client=TestClient(m.app)
    response=client.post('/api/visual-reselect',json={'mode':'ai','clips':rows,'topic':'winter fails','blur_text':False})
    assert response.status_code==202,response.text
    identity=response.json()['id']
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        job=client.get('/api/jobs/'+identity).json()
        if job['status'] in ('done','failed'):break
        time.sleep(.03)
    assert job['status']=='done',job
    assert len(job['clips'])==5 and job['limit_seconds']==300
    assert all(c['visual_review'] for c in job['clips'])
