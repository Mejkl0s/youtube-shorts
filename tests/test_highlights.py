"""Editorial protocol fixtures plus real decoded video/cut/export verification."""
import copy
import threading
import uuid
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main as m, highlights as h, event_signals, work_budget as work
from backend.timeline import choose_moments
from backend import visual_selection as v
from test_workflow import isolated, make_source
from test_visual_selection import candidates


def entries(count=100):
    return [{'url':('https://www.tiktok.com/@fixture/video/'+str(7000000000000000000+i) if i%3==0 else
                    'https://www.instagram.com/reel/FIXTURE'+str(i) if i%3==1 else
                    'https://www.youtube.com/shorts/FIXTURE'+f'{i:04d}'),
             'title':f'Winter fails {i}'} for i in range(count)]


def test_search_queries_youtube_from_start_balances_sources_and_inherits_budget(monkeypatch):
    gate=threading.Barrier(2);seen=[];budget=work.Budget(30)
    def public(*args,**kwargs):
        assert work.current() is budget and kwargs['balanced'] is True
        seen.append('public');gate.wait(timeout=5)
        return entries(100),['one indexed source unavailable']
    def youtube(*args,**kwargs):
        assert work.current() is budget and kwargs['fallback'] is False
        seen.append('youtube');gate.wait(timeout=5)
        return [entries(3)[2]],[]
    monkeypatch.setattr(m,'public_search',public);monkeypatch.setattr(m,'youtube_search',youtube)
    token=work._active.set(budget)
    try:rows,warnings=h.search(m.DiscoverRequest(topic='winter fails',candidate_count=100))
    finally:work._active.reset(token)
    assert set(seen)=={'public','youtube'} and len(rows)==100
    assert len({m.canonical_url(row['url']) for row in rows})==100
    counts={name:sum(m.source_name(row['url'])==name for row in rows) for name in ('TikTok','Instagram','YouTube')}
    assert max(counts.values())-min(counts.values())<=1
    assert warnings==['one indexed source unavailable']


def test_thorough_downloads_24_then_reviews_every_candidate_and_reports_sources(isolated,monkeypatch):
    monkeypatch.setattr(h,'search',lambda body:(entries(),[]));downloads=[];reviews=[]
    def download(item):
        downloads.append(item)
        return {'id':uuid.uuid4().hex,'duration':6,'source':item['source'],'source_url':item['url'],'content_sha256':str(len(downloads))}
    def select(rows,body,report):
        for candidate in rows:reviews.append(candidate);report(candidate,True)
        return []
    monkeypatch.setattr(m,'download_candidate',download);monkeypatch.setattr(h,'select',select)
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity,'kind':'discover'}
    h.discover(identity,m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough',candidate_count=100,blur_text=False))
    result=m.jobs[identity]
    assert len(downloads)==len(reviews)==24  # No early exit at the first five/six.
    assert result['status']=='failed' and not result['partial_clips']
    assert len(result['downloaded_sources'])==24 and len(result['search_results'])==100
    assert all(row['downloaded']==row['reviewed']==row['accepted']==8 for row in result['source_stats'].values())
    assert result['max_duration']==25


def test_blocked_instagram_does_not_abort_other_sources(isolated,monkeypatch):
    monkeypatch.setattr(h,'search',lambda body:(entries(),[]));attempts=[]
    def download(item):
        attempts.append(item['source'])
        if item['source']=='Instagram':raise m.CandidateDownloadError('login_required','Přihlášení je vyžadováno.')
        return {'id':uuid.uuid4().hex,'source':item['source'],'source_url':item['url']}
    monkeypatch.setattr(m,'download_candidate',download);monkeypatch.setattr(h,'select',lambda *args:[])
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity}
    h.discover(identity,m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough',candidate_count=100,blur_text=False))
    assert attempts.count('Instagram')==2 and attempts.count('YouTube')==12 and attempts.count('TikTok')==12
    assert m.jobs[identity]['source_stats']['Instagram']['failed']==2
    assert any('Přihlášení' in note for note in m.jobs[identity]['warnings'])


def test_thorough_requires_visual_ai_and_does_not_start_paid_fallback(isolated,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('no paid call')
    monkeypatch.setattr(m,'ai_request',forbidden)
    response=TestClient(m.app).post('/api/discover',json={'topic':'winter fails','search_depth':'thorough','mode':'free'})
    assert response.status_code==409 and not m.jobs


def test_cancelled_thorough_keeps_downloaded_sources_and_audited_partial(isolated,monkeypatch):
    monkeypatch.setattr(h,'search',lambda body:(entries(3),[]))
    monkeypatch.setattr(m,'download_candidate',lambda item:{'id':uuid.uuid4().hex,'source':m.source_name(item['url'])})
    budget=work.Budget();budget.visual_clips=[{'id':'audited'}]
    def stop(*args):raise work.WorkStopped(True)
    monkeypatch.setattr(h,'select',stop);token=work._active.set(budget)
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity}
    try:
        with pytest.raises(work.WorkStopped):h.discover(identity,m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough'))
    finally:work._active.reset(token)
    assert len(m.jobs[identity]['downloaded_sources'])==3
    assert m.jobs[identity]['partial_clips']==[{'id':'audited'}]


def editorial_fixture(monkeypatch):
    calls=[];reviewed=[]
    def request(prompt,evidence,tokens=3500):
        calls.append((prompt,evidence))
        if 'PER-VIDEO SCOUT' in prompt:return {'shortlist':[{'start':5.5,'end':7.5,'action':6.5}]}
        if 'PER-VIDEO FINAL REVIEW' in prompt:
            reviewed.append(evidence[0]['text'])
            return {'moments':[{'scene':0,'topic_match':True,'complete':True,'confidence':.95,'score':70+len(reviewed),
                'start':5.5,'end':7.5,'setup':{'time':5.7,'observation':'Preparation visible'},
                'action':{'time':6.5,'observation':'Main event'},'outcome':{'time':7.1,'observation':'Visible result'},
                'title':'Late visible event','voiceover':'The late result.','rank_note':'Late result','reason':'Visible preparation and result.'}]}
        if 'CUT AUDIT' in prompt:return {'accepted':True,'topic_match':True,'complete':True,'action_visible':True,'outcome_visible':True,'confidence':.95,'reason':'The completed event is visible.'}
        if 'SET AUDIT' in prompt:return {'distinct':True,'duplicates':[],'confidence':.9,'reason':'Different visible events.'}
        raise AssertionError(prompt)
    monkeypatch.setattr(v,'request',request)
    return calls,reviewed,request


def test_real_review_decodes_late_event_short_cuts_and_exports_without_padding(isolated,monkeypatch):
    sources=candidates(isolated,(8,)*7)
    calls,reviewed,_=editorial_fixture(monkeypatch)
    clips=h.select(sources,m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough'),lambda *args:None)
    assert len(reviewed)==7 and len(clips)==5
    assert len([p for p,_ in calls if 'CUT AUDIT' in p])==5
    assert len([p for p,_ in calls if 'SET AUDIT' in p])==1
    assert {c['source_asset_id'] for c in clips}=={c['id'] for c in sources[2:]}
    assert sum(c['duration'] for c in clips)==pytest.approx(10,abs=.05)
    for clip in clips:
        assert clip['start']==0 and clip['source_start']==5.5 and clip['has_audio']
        assert m.asset(clip['id'])['visual_review']['cut_audit']['accepted']
        assert clip['visual_review']['method']=='adaptive-event-v3'
    project=m.Project(title='Short actual moments',clips=[m.Clip.model_validate(c) for c in clips],voice=False,effects=True,resolution='720',max_duration=25)
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity};m.render(identity,project)
    assert m.jobs[identity]['status']=='done',m.jobs[identity]
    meta=m.probe(isolated/'jobs'/identity/'ranking.mp4')
    assert float(meta['format']['duration'])<10.2<25
    assert {s['codec_type'] for s in meta['streams']}=={'video','audio'}


def test_rejected_cut_and_cross_platform_repost_are_replaced(isolated,monkeypatch):
    sources=candidates(isolated,(8,)*8)
    _,reviewed,original=editorial_fixture(monkeypatch);audits=[];sets=[]
    def request(prompt,evidence,tokens=3500):
        if 'CUT AUDIT' in prompt:
            audits.append(evidence)
            if len(audits)==1:return {'accepted':False}
        if 'SET AUDIT' in prompt:
            sets.append(evidence)
            if len(sets)==1:return {'distinct':False,'duplicates':[{'duplicate':1,'original':0}],'confidence':.95,'reason':'Same fall reposted with another crop.'}
        return original(prompt,evidence,tokens)
    monkeypatch.setattr(v,'request',request)
    result=h.select(sources,m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough'),lambda *args:None)
    assert len(reviewed)==8 and len(result)==5 and len(audits)==7 and len(sets)==2
    assert len({c['source_asset_id'] for c in result})==5


@pytest.mark.parametrize('proposal',[None,{'start':0,'end':8,'action':9},{'start':0,'end':9,'action':3}, {'start':float('nan'),'end':6,'action':3}])
def test_invalid_scout_never_becomes_a_clip(isolated,monkeypatch,proposal):
    source=candidates(isolated,(8,))[0]
    monkeypatch.setattr(v,'request',lambda *args:{'shortlist':[proposal]})
    with pytest.raises(v.VisualSelectionError):h.review_video(source,'winter fails','en','Surprise')


def test_low_or_invalid_cut_audit_confidence_is_rejected(isolated,monkeypatch):
    source=candidates(isolated,(8,))[0]
    clip={**source,'source_start':0,'visual_review':{'action':{'time':4}}}
    for confidence in (.79,1.1):
        monkeypatch.setattr(v,'request',lambda *args:{'accepted':True,'topic_match':True,'complete':True,'action_visible':True,'outcome_visible':True,'confidence':confidence,'reason':'Seen'})
        assert not h.audit(clip,'winter fails')


def test_rgb_activity_hints_distinguish_local_action_from_uniform_color(monkeypatch):
    static=np.zeros((30,54,96,3),dtype=np.uint8)
    local=static.copy();local[24:,12:40,24:60]=255
    color=static.copy();color[24:]=255
    for images,local_expected in ((local,True),(color,False)):
        monkeypatch.setattr(m,'ffmpeg',lambda *args,**kwargs:images.tobytes())
        peaks=event_signals.scan(Path('fixture'),10)
        assert any(7.5<p['time']<8.5 for p in peaks)
        peak=max(peaks,key=lambda row:row['score'])
        assert (peak['motion']>.5) is local_expected
        assert peak['color']>0


def test_camera_translation_is_not_localized_action(monkeypatch):
    rng=np.random.default_rng(42);image=rng.integers(0,255,(54,96,3),dtype=np.uint8)
    images=np.stack([image if i%2==0 else np.roll(image,4,axis=1) for i in range(9)])
    monkeypatch.setattr(m,'ffmpeg',lambda *args,**kwargs:images.tobytes())
    assert event_signals.scan(Path('fixture'),3)==[]


def test_dense_samples_and_late_rgb_peak_are_from_real_source(isolated):
    source=candidates(isolated,(12,))[0];path=isolated/'media'/source['id']/'source'
    peaks=event_signals.scan(path,12)
    assert any(10.5<=row['time']<=11.5 for row in peaks)
    samples=h.samples(path,8,12,11)
    assert samples[0][0]==8 and samples[-1][0]>11.8
    assert len([at for at,_ in samples if 10.4<=at<=11.5])>=8
    assert all(at<12 for at,_ in samples)


def test_25s_ceiling_selects_whole_short_alternatives_and_does_not_pad():
    rows=[{'id':i,'duration':6 if i<5 else 2,'score':1 if i<5 else .99} for i in range(10)]
    result=choose_moments(rows,duration=lambda r:r['duration'],score=lambda r:r['score'],identity=lambda r:r['id'],source=lambda r:r['id'],max_seconds=25,brevity=True)
    assert len(result)==5 and sum(r['duration'] for r in result)==10
    assert all(r['duration']==2 for r in result)
    legacy=choose_moments(rows[:5],duration=lambda r:r['duration'],score=lambda r:r['score'],identity=lambda r:r['id'],source=lambda r:r['id'])
    assert len(legacy)==5 and sum(r['duration'] for r in legacy)==30
    clips=[{'id':uuid.uuid4().hex,'title':'Event','voiceover':'A result','duration':6} for _ in range(5)]
    assert m.Project(title='Old project',clips=clips).max_duration==40
    with pytest.raises(ValidationError):m.Project(title='New project',clips=clips,max_duration=25)


def test_native_youtube_results_get_space_even_when_public_index_is_full(monkeypatch):
    direct={'url':'https://www.youtube.com/shorts/DIRECT00001','title':'Winter fails direct'}
    monkeypatch.setattr(m,'public_search',lambda *args,**kwargs:(entries(100),[]))
    monkeypatch.setattr(m,'youtube_search',lambda *args,**kwargs:([direct],[]))
    rows,_=h.search(m.DiscoverRequest(topic='winter fails',candidate_count=100))
    assert rows[2]['url']==direct['url'] and len(rows)==100
    called=[]
    monkeypatch.setattr(m,'youtube_search',lambda *args,**kwargs:called.append(True))
    h.search(m.DiscoverRequest(topic='winter fails',allow_youtube=False))
    assert not called


def test_full_scene_detection_keeps_late_shots_and_skips_technical_window_search(monkeypatch):
    import subprocess
    monkeypatch.setattr(m,'probe',lambda path:{'format':{'duration':'60'}})
    monkeypatch.setattr(work,'process_result',lambda *args:subprocess.CompletedProcess([],0,b'',b' '.join(f'pts_time:{i*2}'.encode() for i in range(1,30))))
    monkeypatch.setattr(m,'action_window',lambda *args:pytest.fail('Full AI review must retain physical boundaries, not technical action windows'))
    windows=m.scene_windows(Path('fixture'),full=True)
    assert len(windows)==30 and windows[-1].scene_end==60


def test_thorough_cannot_request_40_second_ranking():
    with pytest.raises(ValidationError,match='25'):
        m.DiscoverRequest(topic='winter fails',search_depth='thorough',mode='local',max_duration=40)


def test_malformed_moment_text_becomes_a_rejected_candidate(isolated,monkeypatch):
    source=candidates(isolated,(8,))[0]
    _,_,original=editorial_fixture(monkeypatch)
    def request(prompt,evidence,tokens):
        result=original(prompt,evidence,tokens)
        if 'PER-VIDEO FINAL REVIEW' in prompt:result['moments'][0]['title']='Too long '*30
        return result
    monkeypatch.setattr(v,'request',request)
    assert h.select([source],m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough'),lambda *args:None)==[]


def test_low_event_score_is_not_used_to_fill_ranking(isolated,monkeypatch):
    source=candidates(isolated,(8,))[0];_,_,original=editorial_fixture(monkeypatch)
    def request(prompt,evidence,tokens):
        result=original(prompt,evidence,tokens)
        if 'PER-VIDEO FINAL REVIEW' in prompt:result['moments'][0]['score']=59
        return result
    monkeypatch.setattr(v,'request',request)
    assert h.select([source],m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough'),lambda *args:None)==[]


def test_uncertain_set_is_not_reported_as_five_verified_distinct_incidents(isolated,monkeypatch):
    sources=candidates(isolated,(8,)*5);_,_,original=editorial_fixture(monkeypatch)
    def request(prompt,evidence,tokens):
        if 'SET AUDIT' in prompt:return {'distinct':True,'duplicates':[],'confidence':.3,'reason':'Unclear differences.'}
        return original(prompt,evidence,tokens)
    monkeypatch.setattr(v,'request',request);budget=work.Budget();token=work._active.set(budget)
    try:result=h.select(sources,m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough'),lambda *args:None)
    finally:work._active.reset(token)
    assert len(result)==4 and budget.visual_clips==result


def test_no_search_results_explains_retrieval_failure_instead_of_ai_rejection(isolated,monkeypatch):
    monkeypatch.setattr(h,'search',lambda body:([],['bing: veřejné vyhledávání nebylo dostupné (HTTP 403).']))
    monkeypatch.setattr(h,'select',lambda *args:pytest.fail('No source was retrieved'))
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity}
    h.discover(identity,m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough'))
    result=m.jobs[identity]
    assert result['status']=='failed' and 'odkazy' in result['message'] and '403' in result['warnings'][0]
    assert not result['downloaded_sources'] and result['partial_clips']==[]


def test_all_downloads_fail_explains_loading_failure_separately(isolated,monkeypatch):
    monkeypatch.setattr(h,'search',lambda body:(entries(3),[]))
    def denied(*args):raise m.CandidateDownloadError('blocked','Video není veřejně dostupné.')
    monkeypatch.setattr(m,'download_candidate',denied)
    monkeypatch.setattr(h,'select',lambda *args:pytest.fail('No downloadable sources'))
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity}
    h.discover(identity,m.DiscoverRequest(topic='winter fails',mode='local',search_depth='thorough'))
    result=m.jobs[identity]
    assert result['status']=='failed' and '3 odkazů' in result['message'] and 'nepodařilo načíst' in result['message']
    assert len(result['download_failures'])==3 and result['partial_clips']==[]
