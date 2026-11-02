import asyncio
import io
import json
from pathlib import Path
import threading
import time
import types
import uuid
import zipfile

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import main as m,desktop_ai as ai,ai_providers as providers,desktop_store as store,desktop_models as models,desktop_api
from backend.access import owner_access
from backend.desktop_secrets import Vault
from test_workflow import isolated


@pytest.fixture
def desktop(isolated,monkeypatch):
    monkeypatch.setenv('RANK_DESKTOP_MODE','1');monkeypatch.setenv('RANK_LOCAL_MODE','1');monkeypatch.setenv('STUDIO_PUBLIC','0')
    monkeypatch.setenv('STUDIO_PASSWORD','');monkeypatch.setenv('RANK_FREE_ONLY','1')
    monkeypatch.setenv('RANK_DESKTOP_TOKEN','fixture-token');monkeypatch.setenv('RANK_DESKTOP_ADMIN_TOKEN','fixture-admin')
    monkeypatch.setattr(models,'_downloads',{});monkeypatch.setattr(models,'_owned',None)
    app=FastAPI();app.middleware('http')(owner_access);app.include_router(ai.router);app.include_router(desktop_api.router);app.include_router(store.exchange_router)
    app.mount('/',m.app)
    client=TestClient(app,base_url='http://127.0.0.1',headers={'X-Rank-Desktop-Token':'fixture-token'})
    yield client
    for row in models._downloads.values():row['cancel'].set();row['thread'].join(3)


def configured(identity='deepseek',model='deepseek-chat',vision=False):
    data=ai.defaults();data['mode']=providers.PROVIDERS[identity]['kind'];data['active']={'provider':identity,'model':model}
    data['providers'][identity].update(enabled=True,models=[{'id':model,'name':model,'vision':vision,'size_bytes':None}],checked_at=time.time())
    if identity=='custom':data['providers'][identity]['endpoint']='https://fixture.invalid/v1'
    ai.save(data);ai.vault().set(ai.credential_scope(data['providers'][identity]),'fixture-secret')
    return data


def test_desktop_rejects_browser_without_session_token_and_native_calls_without_admin(desktop):
    assert desktop.get('/api/health').status_code==200
    assert desktop.get('/api/health',headers={'X-Rank-Desktop-Token':'wrong'}).status_code==403
    assert desktop.post('/api/desktop/migrate',json={'directory':'/etc'}).status_code==403
    assert desktop.get('/api/desktop/state',headers={'Host':'outside.invalid'}).status_code==400
    assert desktop.post('/api/desktop/state',json={'state':{}},headers={'Origin':'https://outside.invalid'}).status_code==403
    assert desktop.get('/').headers['cache-control']=='no-store'
    assert "script-src 'self'" in desktop.get('/').headers['content-security-policy']


@pytest.mark.parametrize('url,kind',[('http://example.com','cloud'),('https://127.0.0.1','cloud'),('https://169.254.169.254','cloud'),
    ('http://192.168.1.2:8080','local'),('http://localhost:0','local'),('http://user:pass@localhost','local'),
    ('http://127.0.0.1?target=elsewhere','local'),('file:///etc/passwd','local'),('http://127.0.0.1\\@outside.invalid','local')])
def test_endpoint_boundaries(url,kind):
    with pytest.raises(providers.ProviderError):providers.endpoint(url,kind)


def test_dpapi_vault_does_not_write_plaintext_on_non_windows(desktop):
    import os
    vault=Vault(ai.root());vault.set('deepseek','a-sensitive-fixture-key')
    assert vault.get('deepseek')=='a-sensitive-fixture-key'
    if os.name!='nt':assert not vault.path.exists()
    else:assert b'a-sensitive-fixture-key' not in vault.path.read_bytes()
    public=desktop.get('/api/desktop/ai/config').text
    assert 'a-sensitive-fixture-key' not in public
    vault.set('deepseek','');assert not vault.get('deepseek')


@pytest.mark.parametrize('identity',providers.PROVIDERS)
def test_discovery_uses_provider_api_and_real_returned_model_ids(desktop,monkeypatch,identity):
    data=ai.defaults();profile=data['providers'][identity]
    if identity=='custom':profile['endpoint']='https://fixture.invalid/v1'
    calls=[]
    def respond(request):
        calls.append(request)
        if identity=='anthropic':assert request.headers['x-api-key']=='fixture-secret'
        elif identity=='gemini':assert request.headers['x-goog-api-key']=='fixture-secret' and 'key=' not in str(request.url)
        else:assert request.headers.get('authorization')=='Bearer fixture-secret'
        if request.url.path=='/api/show':return httpx.Response(200,json={'capabilities':['vision']})
        if identity=='ollama':return httpx.Response(200,json={'models':[{'name':'fixture-vlm:7b','size':6_000_000_000,'digest':'a'*64}]})
        row={'id':'fixture-model-v1','name':'fixture-model-v1','capabilities':{'vision':True}}
        if identity=='deepseek':row={'id':'deepseek-chat'}
        if identity=='gemini':row={'name':'models/gemini-fixture','supportedGenerationMethods':['generateContent']}
        if identity=='openrouter':row['architecture']={'input_modalities':['text','image']}
        return httpx.Response(200,json={'models':[row]} if identity=='gemini' else {'data':[row]})
    original=httpx.Client
    def client(**kwargs):
        assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        return original(transport=httpx.MockTransport(respond),**kwargs)
    monkeypatch.setattr(httpx,'Client',client)
    rows=providers.discover(profile,'fixture-secret')
    assert rows and rows[0]['id'] in ('fixture-model-v1','gemini-fixture','fixture-vlm:7b','deepseek-chat')
    if identity=='deepseek':assert rows[0]['vision'] is False
    assert calls


@pytest.mark.parametrize('identity',['openai','anthropic','gemini','deepseek','openrouter','custom','lmstudio','llamacpp','local'])
def test_distinct_inference_payloads_and_json_decoding(desktop,monkeypatch,identity):
    data=configured(identity,model='fixture-model-v1',vision=identity!='deepseek')
    if identity=='custom':data['providers'][identity]['endpoint']='https://fixture.invalid/v1';ai.save(data)
    captures=[]
    def post(url,**kwargs):
        captures.append((url,kwargs));payload=kwargs['payload']
        assert kwargs['local'] and kwargs['headers']
        if identity=='anthropic':
            assert url.endswith('/messages') and 'system' in payload and 'response_format' not in payload
            result={'content':[{'type':'text','text':'{"text":"answer"}'}]}
        elif identity=='gemini':
            assert url.endswith(':generateContent') and 'contents' in payload and 'messages' not in payload
            result={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"text":"answer"}'}]}}]}
        else:
            assert url.endswith('/chat/completions') and payload['model']=='fixture-model-v1'
            result={'choices':[{'message':{'content':'{"text":"answer"}'},'finish_reason':'stop'}]}
        return httpx.Response(200,request=httpx.Request('POST',url),json=result)
    monkeypatch.setattr(m.work,'post_json',post)
    assert ai.legacy_request({'messages':[{'role':'system','content':'Return JSON'},{'role':'user','content':'Help write a title'}]})=={'text':'answer'}
    assert len(captures)==1


def test_deepseek_is_usable_for_text_but_never_receives_video_frames(desktop,monkeypatch):
    configured();calls=[]
    monkeypatch.setattr(m.work,'post_json',lambda *a,**kw:calls.append(kw))
    with pytest.raises(providers.ProviderError,match='podporu obrázků'):
        ai.request('Judge video',[{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,ZmFrZQ=='}}],100)
    assert calls==[]
    assert not m.local_vision.status()['ready']


def test_model_choice_is_verified_persistent_and_does_not_silently_change_provider(desktop,monkeypatch):
    configured()
    response=desktop.post('/api/desktop/ai/config',json={'mode':'cloud','provider':'deepseek','model':'invented-model'})
    assert response.status_code==400
    monkeypatch.setattr(providers,'discover',lambda *args:[{'id':'deepseek-reasoner','vision':False,'size_bytes':None}])
    response=desktop.post('/api/desktop/ai/providers/deepseek/test')
    assert response.json()['models'][0]['id']=='deepseek-reasoner'
    response=desktop.post('/api/desktop/ai/config',json={'mode':'hybrid','provider':'deepseek','model':'deepseek-reasoner','wizard_complete':True})
    assert response.status_code==200,response.text
    assert ai.load()['active']=={'provider':'deepseek','model':'deepseek-reasoner'}
    assert ai.load()['wizard_complete']
    assert ai.vault().contains(ai.credential_scope(ai.load()['providers']['deepseek']))
    response=desktop.post('/api/desktop/ai/config',json={'mode':'hybrid','provider':'deepseek','model':'deepseek-reasoner','wizard_complete':False})
    assert response.status_code==200 and ai.vault().contains(ai.credential_scope(ai.load()['providers']['deepseek']))


def test_running_job_keeps_original_model_and_key_while_new_job_uses_new_selection(desktop):
    configured();pool=ai.DesktopExecutor(max_workers=1)
    started=threading.Event();resume=threading.Event()
    def first():started.set();assert resume.wait(5);return ai.selected()
    try:
        future=pool.submit(first);assert started.wait(3)
        data=ai.load();data['active']['model']='new-model';data['providers']['deepseek']['models'].append({'id':'new-model','vision':False});ai.save(data);ai.vault().set(ai.credential_scope(data['providers']['deepseek']),'new-secret')
        resume.set();original=future.result(5);new=pool.submit(ai.selected).result(5)
        assert original['model']=='deepseek-chat' and original['key']=='fixture-secret'
        assert new['model']=='new-model' and new['key']=='new-secret'
    finally:resume.set();pool.shutdown()


def test_sqlite_state_and_project_history_survive_reopen_and_failed_import(desktop,isolated):
    state={'rank-studio-project':json.dumps({'title':'Original','clips':[None]*5}),'rank-studio-chat':'[]'}
    assert desktop.post('/api/desktop/state',json={'state':state}).status_code==200
    assert store.state_get()==state
    saved=store.save_project(state)
    assert store.project_get(saved)==state
    assert store.project_list()[0]['title']=='Original'
    invalid=desktop.post('/api/project-exchange/import',files={'file':('bad.rankstudio',b'bad zip')})
    assert invalid.status_code==400 and store.state_get()==state


def test_portable_archive_contains_sources_and_checks_hashes_without_credentials(desktop,isolated):
    identity=uuid.uuid4().hex;folder=isolated/'media'/identity;folder.mkdir();(folder/'source').write_bytes(b'original-media')
    (folder/'metadata.json').write_text(json.dumps({'id':identity,'duration':12}))
    (isolated/'private').mkdir(exist_ok=True);(isolated/'private'/'credentials').write_text('must-not-export')
    state={'rank-studio-project':json.dumps({'title':'Portable','clips':[{'id':identity},None,None,None,None]})}
    bundle=store.make_bundle(state);path=isolated/'private'/'project-exports'/(bundle+'.rankstudio')
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist())=={'project.json',f'media/{identity}/source',f'media/{identity}/metadata.json'}
        manifest=json.loads(archive.read('project.json'));assert manifest['version']==1
    (folder/'source').unlink();(folder/'metadata.json').unlink()
    result=store.import_bundle(path)
    assert result['state']==state and (folder/'source').read_bytes()==b'original-media'
    (folder/'source').write_bytes(b'collision')
    with pytest.raises(ValueError,match='odlišné video'):store.import_bundle(path)
    assert (folder/'source').read_bytes()==b'collision'


@pytest.mark.parametrize('entry',['../outside','/outside','media/../../outside','media\\escape','media/'+'a'*32+'/payload.exe'])
def test_project_archive_rejects_path_traversal_and_executables(desktop,isolated,entry):
    path=isolated/'bad.zip'
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('project.json',json.dumps({'version':1,'state':{},'files':{entry:'a'*64}}));archive.writestr(entry,'payload')
    with pytest.raises(ValueError):store.import_bundle(path)


def test_external_ollama_is_never_terminated_by_app(desktop,monkeypatch):
    original=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'version':'fixture'})),**kw))
    monkeypatch.setattr(models.subprocess,'Popen',lambda *a,**kw:pytest.fail('Attempted to own external Ollama'))
    assert models.start_service()['owned'] is False
    assert models.stop_service()['owned'] is False


def test_owned_local_service_is_actually_stopped(desktop,monkeypatch,tmp_path):
    import subprocess,sys
    monkeypatch.setenv('OLLAMA_MODELS',str(tmp_path/'owned-models'))
    client=httpx.Client;popen=subprocess.Popen;children=[]
    def unavailable(request):raise httpx.ConnectError('fixture service is not running',request=request)
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:client(transport=httpx.MockTransport(unavailable),**kwargs))
    monkeypatch.setattr(models.shutil,'which',lambda name:sys.executable if name=='ollama' else None)
    def start(args,**kwargs):
        if args==[sys.executable,'serve']:args=[sys.executable,'-c','import time;time.sleep(30)']
        process=popen(args,**kwargs);children.append(process);return process
    monkeypatch.setattr(models.subprocess,'Popen',start)
    try:
        assert models.start_service()['owned'] is True
        owned=models._owned
        assert models.stop_service()['owned'] is False
        assert owned.poll() is not None
    finally:
        for child in children:
            if child.poll() is None:child.kill()
            child.wait(timeout=5)


def test_model_removal_requires_matching_confirmation_and_no_active_jobs(desktop,monkeypatch):
    with pytest.raises(Exception) as error:models.delete('qwen2.5vl:7b','wrong')
    assert error.value.status_code==400
    m.jobs['busy']={'status':'working'}
    with pytest.raises(Exception) as error:models.delete('qwen2.5vl:7b','qwen2.5vl:7b')
    assert error.value.status_code==409


def test_hardware_does_not_invent_gpu_memory(desktop,monkeypatch):
    monkeypatch.setattr(models.shutil,'which',lambda name:None)
    facts=models.hardware()
    assert facts['gpus']==[] and 'Nelze zjistit' in facts['acceleration']
    assert facts['disk_free']>0 and facts['recommended'] in ('qwen2.5vl:3b','qwen2.5vl:7b')


def test_ollama_pull_progress_is_real_and_only_reports_done_after_service_verification(desktop,monkeypatch):
    original=httpx.AsyncClient
    events=[{'status':'pulling layer','completed':10,'total':100},{'status':'verifying sha256 digest'},{'status':'success'}]
    def respond(request):
        assert request.url.path=='/api/pull' and request.url.host=='127.0.0.1'
        assert json.loads(request.content)['model']=='qwen2.5vl:7b'
        return httpx.Response(200,content='\n'.join(json.dumps(row) for row in events))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    monkeypatch.setattr(models.shutil,'disk_usage',lambda path:types.SimpleNamespace(free=100*1024**3))
    monkeypatch.setattr(ai,'test_provider',lambda identity:{'ok':True,'models':[{'id':'qwen2.5vl:7b'}]})
    result=models.download('qwen2.5vl:7b');row=models._downloads[result['id']];row['thread'].join(3)
    assert row['state']['status']=='done' and row['state']['percent']==100
    assert row['state']['completed']==10 and row['state']['total']==100


def test_cancelling_model_download_closes_stream_and_keeps_resume_action_available(desktop,monkeypatch):
    original=httpx.AsyncClient;closed=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"status":"pulling","total":100,"completed":20}\n'
            await asyncio.sleep(30)
        async def aclose(self):closed.append(True)
    async def respond(request):return httpx.Response(200,stream=Stream())
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    monkeypatch.setattr(models.shutil,'disk_usage',lambda path:types.SimpleNamespace(free=100*1024**3))
    result=models.download('qwen2.5vl:7b');row=models._downloads[result['id']]
    deadline=time.monotonic()+2
    while row['state']['completed']!=20 and time.monotonic()<deadline:time.sleep(.01)
    models.cancel_download(result['id']);row['thread'].join(3)
    assert row['state']['status']=='cancelled' and closed
    assert not row['thread'].is_alive()


def test_voice_download_resumes_public_bytes_and_checks_pinned_manifest(desktop,monkeypatch):
    import hashlib
    from scripts import download_models
    name=m.VOICE_NAMES['en'];contents={name+'.onnx':b'fixture-model-bytes',name+'.onnx.json':b'{"audio":{}}','MODEL_CARD':b'fixture license'}
    files={suffix:(len(contents[remote]),hashlib.md5(contents[remote]).hexdigest()) for suffix,remote in [('.onnx',name+'.onnx'),('.onnx.json',name+'.onnx.json'),('MODEL_CARD','MODEL_CARD')]}
    monkeypatch.setattr(download_models,'MANIFEST',{'en':{'name':name,'path':'fixture/','files':files}})
    (m.MODELS/(name+'.onnx.part')).write_bytes(contents[name+'.onnx'][:3]);ranges=[]
    original=httpx.AsyncClient
    def respond(request):
        assert request.url.host=='huggingface.co' and 'authorization' not in request.headers
        data=contents[request.url.path.rsplit('/',1)[-1]];offset=0
        if request.headers.get('range'):offset=int(request.headers['range'].split('=')[1].split('-')[0]);ranges.append(offset)
        return httpx.Response(206 if offset else 200,content=data[offset:],headers={'Content-Range':f'bytes {offset}-{len(data)-1}/{len(data)}'})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    result=models.download('piper:en');row=models._downloads[result['id']];row['thread'].join(3)
    assert row['state']['status']=='done' and ranges==[3]
    assert (m.MODELS/(name+'.onnx')).read_bytes()==contents[name+'.onnx']
    assert not (m.MODELS/(name+'.onnx.part')).exists()


def test_bad_ai_config_does_not_prevent_offline_editor_health_or_overwrite_config(desktop):
    path=ai.root()/'ai.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text('broken')
    response=desktop.get('/api/health')
    assert response.status_code==200 and response.json()['local_vision']['ready'] is False
    assert path.read_text()=='broken'


def test_provider_errors_do_not_echo_provider_response_secrets_or_retry_inference(desktop,monkeypatch):
    configured();calls=[]
    def post(url,**kw):
        calls.append(url)
        return httpx.Response(429,request=httpx.Request('POST',url),json={'error':'fixture-secret should not be shown'})
    monkeypatch.setattr(m.work,'post_json',post)
    with pytest.raises(providers.ProviderError) as error:ai.legacy_request({'messages':[{'role':'user','content':'Return JSON'}]})
    assert '429' in str(error.value) and 'fixture-secret' not in str(error.value) and len(calls)==1


def test_technical_free_job_and_manual_ocr_never_use_configured_cloud(desktop,monkeypatch):
    configured('openai','gpt-4o',True)
    monkeypatch.setattr(m.work,'post_json',lambda *a,**kw:pytest.fail('Cloud request in free operation'))
    assert ai.overlay_review_allowed() is False
    pool=ai.DesktopExecutor(max_workers=1)
    def operation(identity,body):
        assert ai.selected()=={} and not ai.overlay_review_allowed()
        with pytest.raises(providers.ProviderError):ai.request('OVERLAY REVIEW',[],100)
    identity=uuid.uuid4().hex;m.jobs[identity]={'status':'queued'}
    try:pool.submit(operation,identity,types.SimpleNamespace(mode='free')).result(3)
    finally:pool.shutdown()


def test_custom_endpoint_change_never_forwards_old_key_to_new_origin(desktop,monkeypatch):
    data=configured('custom','fixture-model',True);original=data['providers']['custom'].copy()
    old_scope=ai.credential_scope(original)
    changed={**original,'endpoint':'https://second.invalid/v1'}
    response=desktop.post('/api/desktop/ai/config',json={'mode':'cloud','provider':'custom','model':'fixture-model','providers':{'custom':changed}})
    assert response.status_code==200 and not response.json()['providers']['custom']['has_key']
    assert ai.selected()=={} and ai.vault().contains(old_scope)
    monkeypatch.setattr(providers,'discover',lambda *a:pytest.fail('Old key was forwarded to new authority'))
    assert desktop.post('/api/desktop/ai/providers/custom/test').json()['ok'] is False
    assert ai.credential(original)=='fixture-secret'
    assert ai.credential({**original,'endpoint':'https://fixture.invalid/v2'})=='fixture-secret'


def test_migration_rejects_escaped_source_and_keeps_original_files(desktop,tmp_path):
    import os,subprocess
    source=tmp_path/'old-studio';source.mkdir();(source/'media').mkdir()
    outside=tmp_path/'outside';outside.mkdir();secret=outside/'private.json';secret.write_text('fixture-private')
    linked=source/'templates'
    if os.name=='nt':
        subprocess.run(['cmd','/c','mklink','/J',str(linked),str(outside)],check=True,capture_output=True)
    else:linked.symlink_to(outside,target_is_directory=True)
    response=desktop.post('/api/desktop/migrate',json={'directory':str(source)},headers={'X-Rank-Desktop-Admin':'fixture-admin'})
    assert response.status_code==400 and secret.read_text()=='fixture-private'
    assert not (store.root()/'templates'/'private.json').exists()


@pytest.mark.parametrize('identity',['deepseek','anthropic','gemini','ollama'])
def test_provider_stream_uses_its_native_format_and_hardened_connection(desktop,monkeypatch,identity):
    configured(identity,'fixture-model',True)
    events={'deepseek':{'choices':[{'delta':{'content':'hello'}}]},
            'anthropic':{'delta':{'text':'hello'}},
            'gemini':{'candidates':[{'content':{'parts':[{'text':'hello'}]}}]},
            'ollama':{'message':{'content':'hello'}}}
    calls=[];original=httpx.Client
    def respond(request):
        if request.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'fixture-model','size':100_000_000,'digest':'a'*64}]})
        if request.url.path=='/api/show':return httpx.Response(200,json={'capabilities':['vision']})
        calls.append(request)
        payload=json.loads(request.content)
        if identity=='gemini':assert request.url.query==b'alt=sse'
        else:assert payload['stream'] is True
        content=json.dumps(events[identity])
        return httpx.Response(200,content=(content+'\n' if identity=='ollama' else 'data: '+content+'\n\ndata: [DONE]\n\n'))
    def client(**kwargs):
        assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        return original(transport=httpx.MockTransport(respond),**kwargs)
    monkeypatch.setattr(httpx,'Client',client)
    assert list(providers.stream(ai.snapshot(),[{'role':'user','content':'Return JSON'}]))==['hello']
    assert len(calls)==1


def test_local_stream_rejects_model_replaced_with_cloud_alias(desktop,monkeypatch):
    configured('ollama','fixture-model',True);original=httpx.Client
    monkeypatch.setattr(providers,'read',lambda *args:{'models':[{'name':'fixture-model','size':100_000_000,'digest':'a'*64}]})
    def respond(request):
        assert request.url.path=='/api/show'
        return httpx.Response(200,json={'remote_host':'https://cloud.invalid'})
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    with pytest.raises(providers.ProviderError,match='cloudový alias'):
        list(providers.stream(ai.snapshot(),[{'role':'user','content':'Return JSON'}]))
