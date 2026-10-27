import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main as m
from backend.source_identity import file_hash, original_hash
from test_workflow import isolated


def raw_asset(data, root, parent=None):
    identity=uuid.uuid4().hex
    folder=root/'media'/identity;folder.mkdir()
    (folder/'source').write_bytes(data)
    meta={'id':identity,'name':'Original','duration':20,'content_sha256':file_hash(folder/'source')}
    if parent:meta['source_asset_id']=parent
    (folder/'metadata.json').write_text(json.dumps(meta))
    return meta


def test_cut_uses_original_identity_including_legacy_metadata(isolated):
    original=raw_asset(b'original full video',isolated)
    child=raw_asset(b'only four seconds',isolated,original['id'])
    assert original_hash(child['id'])==original['content_sha256']
    path=isolated/'media'/original['id']/'metadata.json'
    meta=json.loads(path.read_text());del meta['content_sha256'];path.write_text(json.dumps(meta))
    assert original_hash(child['id'])==original['content_sha256']


def test_identical_file_under_new_url_is_rejected_before_preparation(isolated,monkeypatch):
    original=raw_asset(b'identical downloaded video bytes',isolated)
    def download(args,timeout):
        output=Path(args[args.index('-o')+1].replace('%(ext)s','mp4'))
        output.write_bytes(b'identical downloaded video bytes')
        return b''
    monkeypatch.setattr(m,'run',download)
    monkeypatch.setattr(m,'register',lambda *args:pytest.fail('Duplicate was decoded/prepared'))
    with pytest.raises(m.CandidateDownloadError) as error:
        m.download_candidate({'url':'https://www.youtube.com/shorts/NEWSNOW0001','title':'Winter fails',
                              '_excluded_content':{original['content_sha256']}})
    assert error.value.kind=='duplicate'
    assert len(list((isolated/'media').iterdir()))==1
    assert (isolated/'media'/original['id']/'source').read_bytes()==b'identical downloaded video bytes'


def test_discovery_compares_prior_original_even_without_saved_url(isolated,monkeypatch):
    original=raw_asset(b'old complete source',isolated)
    child=raw_asset(b'old four-second cut',isolated,original['id'])
    rows=[{'url':f'https://www.youtube.com/shorts/NEWSNOW{i:04d}','title':'Winter fails'} for i in range(6)]
    monkeypatch.setattr(m,'public_search',lambda *args:(rows,[]))
    def download(args,timeout):
        index=int(args[-1][-4:]);output=Path(args[args.index('-o')+1].replace('%(ext)s','mp4'))
        output.write_bytes(b'old complete source' if index==0 else f'new source {index}'.encode())
        return b''
    monkeypatch.setattr(m,'run',download)
    monkeypatch.setattr(m,'register',lambda path,identity,name:raw_registered(path,identity,name))
    def raw_registered(path,identity,name):
        return {'id':identity,'name':name,'duration':12,'content_sha256':file_hash(path)}
    monkeypatch.setattr(m,'select_free',lambda rows,topic:rows[:5])
    job=uuid.uuid4().hex;m.jobs[job]={'id':job}
    m.discover(job,m.DiscoverRequest(topic='winter fails',blur_text=False,exclude_asset_ids=[child['id']]))
    result=m.jobs[job]
    assert result['status']=='done' and len(result['clips'])==5
    assert result['download_failures'][0]['kind']=='duplicate'
    assert rows[0]['url'] not in [c['source_url'] for c in result['clips']]
    assert all(c['content_sha256']!=original['content_sha256'] for c in result['clips'])


def test_invalid_asset_history_is_rejected_before_starting_work(isolated):
    response=TestClient(m.app).post('/api/discover',json={'topic':'winter fails','exclude_asset_ids':['../private']})
    assert response.status_code==422


def test_cleanup_supports_complete_thirty_second_window():
    assert m.CleanupRequest(id='a'*32,duration=30).duration==30
    with pytest.raises(ValueError):m.CleanupRequest(id='a'*32,duration=31)


@pytest.mark.parametrize('avoid',[True,False])
def test_chat_discovery_obeys_source_reuse_setting(isolated,monkeypatch,avoid):
    from backend import assistant as a
    clip={'id':uuid.uuid4().hex,'title':'Winter fail','voiceover':'','source_url':'https://www.youtube.com/watch?v=NEWSNOW0001','duration':4}
    monkeypatch.setattr(m,'asset',lambda identity:{'id':identity,'name':'Winter fail','duration':20})
    monkeypatch.setattr(a,'plan_request',lambda body:a.Plan(reply='Hledám další zdroje.',actions=['discover']))
    seen=[]
    def discover(child,body):
        seen.append(body)
        m.set_job(child,status='failed',message='No new sources')
    monkeypatch.setattr(m,'discover',discover)
    job=uuid.uuid4().hex;m.jobs[job]={'id':job,'kind':'assistant'}
    a.run_assistant(job,a.Request(message='Find other winter fails',state=a.State(topic='winter fails',avoid_repeats=avoid,clips=[clip])))
    assert len(seen)==1
    assert seen[0].exclude_asset_ids==([clip['id']] if avoid else [])
    assert seen[0].exclude_urls==([clip['source_url']] if avoid else [])
