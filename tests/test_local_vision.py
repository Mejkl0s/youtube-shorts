import asyncio
import json
import re
import types
import uuid

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import main as m
from backend import local_vision as local
from backend import work_budget as work
from test_workflow import isolated
from test_visual_selection import candidates


@pytest.fixture
def local_pc(monkeypatch,tmp_path):
    monkeypatch.setenv('RANK_LOCAL_MODE','1')
    monkeypatch.setenv('STUDIO_PUBLIC','0')
    monkeypatch.setattr(local,'_status_cache',None)
    monkeypatch.setattr(local,'model_path',lambda:tmp_path/'private'/'local-vision.json')
    return {'supported':True,'ready':True,'model':local.MODEL,'message':'Local fixture ready'}


@pytest.mark.parametrize('cloud,size,vision,ready',[(False,3_200_000_000,True,True),
    (True,3_200_000_000,True,False),(False,0,True,False),(False,3_200_000_000,False,False)])
def test_status_requires_local_file_and_vision_capability(local_pc,monkeypatch,cloud,size,vision,ready):
    calls=[]
    def respond(request):
        calls.append(request)
        assert request.url.host=='127.0.0.1' and request.url.port==11434
        assert 'authorization' not in request.headers
        if request.url.path=='/api/tags':
            return httpx.Response(200,json={'models':[{'name':local.MODEL,'size':size,'digest':'a'*64}]})
        return httpx.Response(200,json={'capabilities':['vision'] if vision else [],'remote_host':'cloud.invalid' if cloud else ''})
    original=httpx.Client
    def client(**kwargs):
        assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        return original(transport=httpx.MockTransport(respond),**kwargs)
    monkeypatch.setattr(httpx,'Client',client)
    monkeypatch.setenv('OLLAMA_HOST','https://cloud.invalid')
    assert local.status()['ready'] is ready
    assert calls


def test_public_host_does_not_probe_pc_or_launch_installer(monkeypatch):
    monkeypatch.setenv('RANK_LOCAL_MODE','1');monkeypatch.setenv('STUDIO_PUBLIC','1')
    monkeypatch.setattr(httpx,'Client',lambda **kw:pytest.fail('Public host probed loopback'))
    assert local.status()=={'supported':False,'ready':False,'model':local.MODEL,'message':'AI zdarma běží na tvém PC, nikoli na bezplatném Renderu.'}
    with pytest.raises(HTTPException) as error:local.start_setup()
    assert error.value.status_code==409


@pytest.mark.parametrize('listing',[[],{'models':None},{'models':[None]}, {'models':'unexpected'}])
def test_unexpected_local_service_reply_does_not_break_studio_health(local_pc,monkeypatch,listing):
    original=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=listing)),**kw))
    assert local.status()['ready'] is False


def test_native_request_uses_no_proxy_key_or_paid_fallback(local_pc,monkeypatch):
    monkeypatch.setattr(local,'status',lambda **kw:local_pc)
    monkeypatch.setattr(m,'ai_request',lambda *a,**kw:pytest.fail('Paid request'))
    captured=[]
    def post(url,**kwargs):
        captured.append((url,kwargs))
        return httpx.Response(200,request=httpx.Request('POST',url),json={'message':{'content':'{"shortlist":[]}'}})
    monkeypatch.setattr(work,'post_json',post)
    result=local.request('SCOUT PASS',[{'type':'text','text':'Actual scene'},
             {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,fixture'}}],1200)
    assert result=={'shortlist':[]}
    url,args=captured[0]
    assert url=='http://127.0.0.1:11434/api/chat' and args['headers']=={} and args['local'] is True
    payload=args['payload']
    assert payload['model']==local.MODEL and payload['format']=='json' and payload['stream'] is False
    assert payload['messages'][1]['images']==['fixture']
    assert not any('api_key' in key.lower() for key in payload)
    monkeypatch.setattr(work,'post_json',lambda *a,**kw:(_ for _ in ()).throw(httpx.ConnectError('Unavailable')))
    with pytest.raises(local.LocalVisionError,match='placené API se nepoužilo'):
        local.request('SCOUT PASS',[],1200)


def test_detailed_local_review_is_split_without_dropping_images(local_pc,monkeypatch):
    calls=[]
    def call(prompt,evidence,tokens):
        calls.append(evidence)
        return {'moments':[{'scene':len(calls)-1}]}
    monkeypatch.setattr(local,'_call',call)
    evidence=[]
    for i in range(3):
        evidence += [{'type':'text','text':f'Scene {i}'}]+[{'type':'image_url','image_url':{'url':f'page {i}/{j}'}} for j in range(4)]
    assert local.request('FINAL REVIEW',evidence,3500)=={'moments':[{'scene':0},{'scene':1},{'scene':2}]}
    assert len(calls)==3 and all(len(call)==5 for call in calls)


def test_local_workflow_uses_real_frames_and_cuts_without_cloud_calls(isolated,local_pc,monkeypatch):
    sources=candidates(isolated)
    rows=[{'url':f'https://www.tiktok.com/@winter/video/{500000+i}','title':'Winter fails'} for i in range(5)]
    monkeypatch.setattr(m,'public_search',lambda *a:(rows,[]))
    monkeypatch.setattr(m,'download_candidate',lambda item:sources[int(item['url'][-6:])-500000])
    monkeypatch.setattr(local,'status',lambda **kw:local_pc)
    monkeypatch.setenv('OPENAI_API_KEY','must-never-be-used')
    monkeypatch.setattr(m,'ai_request',lambda *a,**kw:pytest.fail('Paid AI used'))
    monkeypatch.setattr(m,'ai_search',lambda *a,**kw:pytest.fail('Paid search used'))
    calls=[]
    def native(url,**kwargs):
        calls.append(kwargs)
        assert kwargs['local'] is True and url.startswith(local.BASE)
        payload=kwargs['payload'];prompt=payload['messages'][0]['content'];text=payload['messages'][1]['content']
        assert payload['messages'][1]['images']
        if 'SCOUT PASS' in prompt:
            values=re.findall(r'Scene (\d+)\..*?Bounds ([\d.]+)–([\d.]+)s',text)
            answer={'shortlist':[{'scene':int(i),'start':float(a),'end':float(b)-.2} for i,a,b in values]}
        else:
            i,a,b=re.search(r'Scene (\d+)\..*?covers ([\d.]+)–([\d.]+)s',text).groups()
            i=int(i);a=float(a);b=float(b)
            answer={'moments':[{'scene':i,'topic_match':True,'complete':True,'confidence':.9,'score':20+i*10,
                'start':a,'end':b,'setup':{'time':a+.5,'observation':'Visible setup'},
                'action':{'time':b-1.5,'observation':'Visible action'},'outcome':{'time':b-.2,'observation':'Visible outcome'},
                'title':f'Local event {i}','voiceover':'The ending appears.','rank_note':f'Late result {i}','reason':'Fixture visible sequence.'}]}
        return httpx.Response(200,request=httpx.Request('POST',url),json={'message':{'content':json.dumps(answer)}})
    monkeypatch.setattr(work,'post_json',native)
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity,'kind':'discover'}
    m.discover(identity,m.DiscoverRequest(topic='winter fails',mode='local',blur_text=False))
    job=m.jobs[identity]
    assert job['status']=='done',job
    assert job['limit_seconds']==600 and len(calls)==6
    assert len(job['clips'])==5 and all(c['has_audio'] and c['duration']>4 for c in job['clips'])
    assert all(c['visual_review']['provider']=='local' for c in job['clips'])


def test_missing_local_engine_is_explicit_and_never_switches_to_paid(isolated,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','must-never-be-used')
    monkeypatch.setattr(m,'ai_request',lambda *a:pytest.fail('Paid fallback'))
    monkeypatch.setattr(local,'status',lambda **kw:{'ready':False,'message':'Prepare free model'})
    response=TestClient(m.app).post('/api/discover',json={'topic':'winter fails','mode':'local'})
    assert response.status_code==409 and response.json()['detail']=='Prepare free model'


def test_empty_public_search_never_invokes_ai_search_in_local_mode(isolated,local_pc,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','must-never-be-used')
    monkeypatch.setattr(m,'public_search',lambda *a:([],[]))
    monkeypatch.setattr(m,'youtube_search',lambda *a:([],[]))
    monkeypatch.setattr(m,'ai_search',lambda *a:pytest.fail('Paid search'))
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity}
    m.discover(identity,m.DiscoverRequest(topic='winter fails',mode='local',blur_text=False))
    assert m.jobs[identity]['status']=='failed' and m.jobs[identity]['partial_clips']==[]


def test_free_only_server_blocks_paid_routes_and_voices_even_for_old_clients(isolated,monkeypatch):
    from scripts.local_studio import local_environment
    from backend.style import VoiceSettings
    monkeypatch.setenv('RANK_FREE_ONLY','1')
    monkeypatch.setenv('OPENAI_API_KEY','must-never-be-used')
    monkeypatch.setenv('ELEVENLABS_API_KEY','must-never-be-used')
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:pytest.fail('Paid network request'))
    assert local_environment()['RANK_FREE_ONLY']=='1'
    assert m.health()['free_only'] and not m.health()['ai_scripts'] and not m.health()['elevenlabs']
    with pytest.raises(ValueError,match='vypnuté'):m.ai_request({})
    for provider in ('openai','elevenlabs'):
        with pytest.raises(ValueError,match='vypnuté'):
            m.synthesize('Never charged.','en',isolated/'no.wav',VoiceSettings(provider=provider,voice='onyx' if provider=='openai' else 'adam'))
    client=TestClient(m.app)
    assert client.post('/api/discover',json={'topic':'winter fails','mode':'ai'}).status_code==409
    assert client.post('/api/compilation',json={'id':'a'*32,'mode':'ai'}).status_code==409
    assert client.post('/api/research',json={'topic':'winter fails'}).status_code!=200
    rows=[{'id':uuid.uuid4().hex,'title':'Moment','voiceover':''} for _ in range(5)]
    assert client.post('/api/scripts',json={'clips':rows,'mode':'ai'}).status_code==409
    assert client.post('/api/scripts',json={'clips':rows,'mode':'rank'}).status_code==200


@pytest.mark.parametrize('model',local.MODEL_OPTIONS)
def test_setup_uses_only_fixed_visible_installer(local_pc,monkeypatch,model):
    import subprocess
    path=local.model_path();path.parent.mkdir();path.write_text(json.dumps({'model':model}))
    monkeypatch.setattr(local,'supported',lambda:True)
    monkeypatch.setattr(local,'os',types.SimpleNamespace(name='nt'))
    monkeypatch.setattr(local,'_setup_process',None)
    monkeypatch.setattr(subprocess,'CREATE_NEW_CONSOLE',16,raising=False)
    calls=[]
    def launch(args,**kwargs):
        calls.append((args,kwargs))
        return types.SimpleNamespace(poll=lambda:None)
    monkeypatch.setattr(subprocess,'Popen',launch)
    assert local.start_setup()['started']
    assert local.start_setup()['started'] and len(calls)==1
    args,kwargs=calls[0]
    assert args==['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(m.ROOT/'scripts/setup_local_vision.ps1'),'-Model',model]
    assert kwargs['creationflags']==16 and kwargs['cwd']==m.ROOT


@pytest.mark.parametrize('model',local.MODEL_OPTIONS)
def test_model_choice_persists_and_drives_native_inference(isolated,local_pc,monkeypatch,model):
    monkeypatch.setattr(local,'_setup_process',None)
    monkeypatch.setattr(local,'status',lambda **kw:{**local_pc,'model':local.selected_model()})
    response=TestClient(m.app,base_url='http://127.0.0.1:8765').post('/api/local-vision/model',json={'model':model})
    assert response.status_code==200,response.text
    assert response.json()['model']==model
    assert json.loads(local.model_path().read_text())=={'model':model}
    assert not local.model_path().with_suffix('.tmp').exists()
    captured=[]
    def post(url,**kwargs):
        captured.append(kwargs['payload'])
        assert url==local.BASE+'/api/chat' and kwargs['headers']=={} and kwargs['local']
        return httpx.Response(200,request=httpx.Request('POST',url),json={'message':{'content':'{"shortlist":[]}'}})
    monkeypatch.setattr(work,'post_json',post)
    monkeypatch.setattr(m,'ai_request',lambda *a,**kw:pytest.fail('Paid API used'))
    assert local.request('SCOUT PASS',[],1000)=={'shortlist':[]}
    assert captured[0]['model']==model and captured[0]['options']['num_ctx']==local.CONTEXT[model]


@pytest.mark.parametrize('value',['qwen2.5vl:72b','qwen2.5vl:7b-cloud','https://cloud.invalid','qwen2.5vl:7b;whoami',None])
def test_model_choice_only_accepts_supported_local_models(isolated,local_pc,value):
    assert TestClient(m.app,base_url='http://127.0.0.1:8765').post('/api/local-vision/model',json={'model':value}).status_code==422
    assert not local.model_path().exists()


@pytest.mark.parametrize('running',['queued','working','rendering','searching','setup','public'])
def test_model_cannot_change_during_work_or_on_public_host(isolated,local_pc,monkeypatch,running):
    monkeypatch.setattr(local,'_setup_process',types.SimpleNamespace(poll=lambda:None) if running=='setup' else None)
    if running=='public':
        monkeypatch.setenv('STUDIO_PUBLIC','1')
        monkeypatch.setenv('STUDIO_PASSWORD','model-choice-test')
        monkeypatch.setenv('STUDIO_USERNAME','owner')
    elif running!='setup':m.jobs['fixture']={'status':running}
    response=TestClient(m.app,base_url='http://127.0.0.1:8765').post('/api/local-vision/model',json={'model':'qwen2.5vl:3b'},auth=('owner','model-choice-test') if running=='public' else None)
    assert response.status_code==409,response.text
    assert not local.model_path().exists()


@pytest.mark.parametrize('stored',['broken','[]','{"model":"remote:cloud"}','{"model":null}'])
def test_invalid_saved_model_defaults_to_known_local_model(local_pc,stored):
    path=local.model_path();path.parent.mkdir();path.write_text(stored)
    assert local.selected_model()==local.MODEL


def test_model_change_invalidates_readiness_cache(isolated,local_pc,monkeypatch):
    original=httpx.Client;calls=[]
    def respond(request):
        calls.append(request.url.path)
        if request.url.path=='/api/tags':
            return httpx.Response(200,json={'models':[{'name':'qwen2.5vl:7b','size':5_000_000_000,'digest':'a'*64}]})
        return httpx.Response(200,json={'capabilities':['vision']})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    monkeypatch.setattr(local,'_setup_process',None)
    assert local.status()['ready']
    count=len(calls)
    assert local.status()['ready'] and len(calls)==count
    state=local.choose_model(local.ModelChoice(model='qwen2.5vl:3b'))
    assert not state['ready'] and state['model']=='qwen2.5vl:3b' and len(calls)>count


@pytest.mark.parametrize('residency',[{'size':8_000_000_000,'size_vram':5_000_000_000},
    {'size':8_000_000_000,'size_vram':9_000_000_000}, {'size':None,'size_vram':0}, 'offline'])
def test_optional_residency_reports_actual_loaded_memory_without_blocking_readiness(local_pc,monkeypatch,residency):
    original=httpx.Client
    def respond(request):
        if request.url.path=='/api/tags':
            return httpx.Response(200,json={'models':[{'name':local.MODEL,'size':5_000_000_000,'digest':'a'*64}]})
        if request.url.path=='/api/show':return httpx.Response(200,json={'capabilities':['vision']})
        if residency=='offline':raise httpx.ConnectError('Optional telemetry unavailable')
        return httpx.Response(200,json={'models':[{'name':local.MODEL,**residency}]})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    state=local.status()
    assert state['ready']
    if isinstance(residency,dict) and residency.get('size_vram')==5_000_000_000:
        assert state['memory']=={'total_bytes':8_000_000_000,'gpu_bytes':5_000_000_000}
    else:assert 'memory' not in state


def test_local_http_cancellation_does_not_leave_inference_request_waiting(monkeypatch):
    aborted=[];original=httpx.AsyncClient
    async def pending(request):
        assert request.url.host=='127.0.0.1'
        try:
            await asyncio.sleep(10)
            return httpx.Response(200,json={})
        finally:aborted.append(True)
    def client(**kw):
        assert kw['trust_env'] is False
        return original(transport=httpx.MockTransport(pending),**kw)
    monkeypatch.setattr(httpx,'AsyncClient',client)
    token=work._active.set(work.Budget(.15))
    try:
        with pytest.raises(work.WorkStopped):
            work.post_json(local.BASE+'/api/chat',headers={},payload={},seconds=240,local=True)
        assert aborted
    finally:work._active.reset(token)


def test_bounded_local_pool_keeps_accepted_events_and_reads_new_sources(monkeypatch):
    from backend import visual_selection as visual
    rows=[{'id':uuid.uuid4().hex,'name':str(i),'duration':12} for i in range(12)]
    monkeypatch.setattr(m,'scene_windows',lambda path:[m.SceneWindow(0,12,0,0,12)])
    budget=work.Budget(600)
    budget.visual_clips=[{**rows[0],'scene_start':0,'scene_end':12}]
    budget_token=work._active.set(budget);provider_token=visual._provider.set('local')
    try:
        scenes=visual.catalogue(rows)
        assert len(scenes)==8 and scenes[0]['candidate']['id']==rows[0]['id']
        assert rows[-1]['id'] in {scene['candidate']['id'] for scene in scenes}
        monkeypatch.setattr(m,'scene_windows',lambda path:[m.SceneWindow(i*3,3,i,i*3,i*3+3) for i in range(24)])
        budget.visual_cache.clear();budget.visual_clips=[]
        scenes=visual.catalogue([rows[0]])
        assert len(scenes)==8 and scenes[0]['shot']==0 and scenes[-1]['shot']==23
    finally:
        visual._provider.reset(provider_token);work._active.reset(budget_token)
