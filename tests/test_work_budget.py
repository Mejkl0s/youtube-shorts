import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from backend import main as m
from backend import free_search as f
from backend import work_budget as w
from test_workflow import isolated, make_source


def test_real_subprocess_is_stopped_at_total_deadline():
    budget=w.Budget(.15)
    token=w._active.set(budget)
    started=time.monotonic()
    try:
        with pytest.raises(w.WorkStopped) as error:
            m.run([sys.executable,'-c','import time;time.sleep(10)'],10)
        assert not error.value.cancelled
        assert time.monotonic()-started<2
    finally:w._active.reset(token)


@pytest.mark.skipif(os.name=='nt',reason='POSIX process-tree assertion; native taskkill needs Windows validation')
def test_deadline_terminates_owned_child_process_tree(tmp_path):
    pidfile=tmp_path/'child.pid'
    child="import time;time.sleep(10)"
    parent=f"import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c',{child!r}]);Path({str(pidfile)!r}).write_text(str(p.pid));time.sleep(10)"
    token=w._active.set(w.Budget(.4))
    try:
        with pytest.raises(w.WorkStopped):m.run([sys.executable,'-c',parent],10)
    finally:w._active.reset(token)
    pid=int(pidfile.read_text())
    stat=Path(f'/proc/{pid}/stat')
    assert not stat.exists() or stat.read_text().split()[2]=='Z'


def test_individual_timeout_does_not_exhaust_whole_job():
    budget=w.Budget(10);token=w._active.set(budget)
    try:
        with pytest.raises(subprocess.TimeoutExpired):m.run([sys.executable,'-c','import time;time.sleep(5)'],.1)
        assert budget.remaining()>8
    finally:w._active.reset(token)


def test_discovery_stops_when_six_candidates_supply_five_scenes(isolated,monkeypatch):
    rows=[{'url':f'https://www.tiktok.com/@winter/video/{100000+i}','title':'Winter fails'} for i in range(40)]
    monkeypatch.setattr(m,'public_search',lambda *args:(rows,[]))
    downloaded=[]
    def download(item):
        downloaded.append(item['url'])
        return {'id':uuid.uuid4().hex,'name':'Winter fails','duration':6}
    def choose(candidates,topic):
        if len(candidates)<5:raise ValueError('More scenes needed')
        return candidates[:5]
    monkeypatch.setattr(m,'download_candidate',download);monkeypatch.setattr(m,'select_free',choose)
    monkeypatch.setattr(m,'youtube_search',lambda *args:pytest.fail('Unnecessary fallback'))
    job=uuid.uuid4().hex;m.jobs[job]={'id':job,'status':'queued'}
    m.discover(job,m.DiscoverRequest(topic='winter fails',candidate_count=40,blur_text=False))
    assert m.jobs[job]['status']=='done' and len(downloaded)==6
    assert m.jobs[job]['elapsed_seconds']>=0 and not w.timing(job)


def test_expired_job_preserves_completed_analyzed_sources(isolated,monkeypatch):
    sources=[make_source(isolated/'media'/uuid.uuid4().hex,color) for color in ('red','blue','green')]
    rows=[{'url':f'https://www.tiktok.com/@winter/video/{100000+i}','title':'Winter fails'} for i in range(4)]
    monkeypatch.setattr(m,'public_search',lambda *args:(rows,[]))
    count=[]
    def download(item):
        count.append(item)
        if len(count)<=3:return sources[len(count)-1]
        w.current().started-=w.current().seconds+1
        w.checkpoint()
    monkeypatch.setattr(m,'download_candidate',download)
    monkeypatch.setattr(m,'youtube_search',lambda *args:pytest.fail('Work continued past deadline'))
    job=uuid.uuid4().hex;m.jobs[job]={'id':job,'kind':'discover','status':'queued'}
    m.discover(job,m.DiscoverRequest(topic='winter fails',blur_text=False))
    result=m.jobs[job]
    assert result['status']=='failed' and 'limit' in result['message']
    assert len(result['partial_clips'])==len(result['downloaded_sources'])==3
    assert all(c['duration']==3 and c['review_required'] for c in result['partial_clips'])
    assert all((isolated/'media'/s['id']/'source').is_file() for s in sources)


def test_cancel_endpoint_keeps_slot_busy_until_real_process_stops(isolated,monkeypatch):
    source=make_source(isolated/'media'/uuid.uuid4().hex,'blue')
    marker=isolated/'waiting'
    rows=[{'url':f'https://www.tiktok.com/@winter/video/{100000+i}','title':'Winter fails'} for i in range(2)]
    monkeypatch.setattr(m,'public_search',lambda *args:(rows,[]))
    calls=[]
    def download(item):
        calls.append(item)
        if len(calls)==1:return source
        marker.write_text('running')
        m.run([sys.executable,'-c','import time;time.sleep(10)'],10)
    monkeypatch.setattr(m,'download_candidate',download)
    monkeypatch.delenv('STUDIO_PUBLIC',raising=False);monkeypatch.delenv('STUDIO_PASSWORD',raising=False)
    client=TestClient(m.app)
    response=client.post('/api/discover',json={'topic':'winter fails','blur_text':False})
    assert response.status_code==202
    job=response.json()['id'];deadline=time.monotonic()+5
    while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
    assert marker.exists()
    assert client.get('/api/jobs/'+job).json()['limit_seconds']==300
    stopped=client.post('/api/jobs/'+job+'/cancel',json={})
    assert stopped.status_code==200 and stopped.json()['cancel_requested']
    assert stopped.json()['status'] not in ('done','failed')
    while time.monotonic()<deadline:
        result=client.get('/api/jobs/'+job).json()
        if result['status']=='failed':break
        time.sleep(.01)
    assert result['cancelled'] and result['candidate_count']==1
    assert len(result['downloaded_sources'])==1
    assert (isolated/'media'/source['id']/'source').is_file()
    assert client.post('/api/jobs/'+uuid.uuid4().hex+'/cancel',json={}).status_code==404
    monkeypatch.setattr(m.executor,'submit',lambda *args:None)
    assert client.post('/api/discover',json={'topic':'winter fails'}).status_code==202


def test_fast_preview_keeps_encoded_video_and_original_audio(isolated):
    identity=uuid.uuid4().hex;folder=isolated/'media'/identity;folder.mkdir()
    path=folder/'source'
    m.ffmpeg('-f','lavfi','-i','testsrc2=s=160x284:r=15:d=3',
             '-f','lavfi','-i','sine=frequency=440:duration=3','-c:v','libx264','-c:a','aac','-f','mp4',str(path))
    meta=m.register(path,identity,'Ready MP4',fast_preview=True)
    preview=folder/'preview.mp4'
    for kind in ('v','a'):
        def digest(p):return m.ffmpeg('-i',str(p),'-map',f'0:{kind}:0','-c','copy','-f','hash','-hash','sha256','pipe:1')
        assert digest(path)==digest(preview)
    assert meta['has_audio'] and float(m.probe(preview)['format']['duration'])>=3


def test_incremental_selection_reuses_completed_source_analysis(isolated,monkeypatch):
    source=make_source(isolated/'media'/uuid.uuid4().hex,'blue')
    original=m.scene_windows;calls=[]
    monkeypatch.setattr(m,'scene_windows',lambda path:calls.append(path) or original(path))
    token=w._active.set(w.Budget(20))
    try:
        assert len(f.select_free([source],'winter fails',require_five=False))==1
        assert len(f.select_free([source],'winter fails',require_five=False))==1
    finally:w._active.reset(token)
    assert len(calls)==1


def test_query_phase_gives_each_source_a_turn_before_extra_variants(monkeypatch):
    from types import SimpleNamespace
    clock=[0];calls=[]
    monkeypatch.setattr(f,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def search(query,engine):
        calls.append(query);clock[0]+=8
        return []
    monkeypatch.setattr(f,'engine_results',search)
    entries,_=f.public_search('winter fails',True,40)
    assert not entries and len(calls)<=5
    assert all(any(domain in query for query in calls) for domain in ('site:tiktok.com','site:instagram.com','site:youtube.com'))


def test_unavailable_public_engines_are_not_retried_by_fallback(monkeypatch):
    calls=[]
    def blocked(query,engine):
        calls.append(engine)
        raise RuntimeError('HTTP 403')
    monkeypatch.setattr(f,'engine_results',blocked)
    token=w._active.set(w.Budget(20))
    try:
        f.public_search('winter fails',True,40)
        f.public_search('winter fails',True,40,only_youtube=True)
    finally:w._active.reset(token)
    assert sorted(calls)==['bing','duckduckgo']
