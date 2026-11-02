"""Official Ollama model operations and hardware facts (unknown stays null)."""
import asyncio
import csv
import ctypes
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import threading
import time
import uuid

import httpx
from fastapi import HTTPException

from . import desktop_ai as ai
from . import ai_providers as providers
from .desktop_secrets import atomic_json

CATALOG=[{'id':'qwen2.5vl:3b','name':'Qwen2.5-VL 3B','estimate':'přibližně 3–4 GB','disk_required':8*1024**3,'ram_recommended':16*1024**3,
          'source':'https://ollama.com/library/qwen2.5vl','license':'Qwen Research License (3B); ověř podmínky u zdroje'},
         {'id':'qwen2.5vl:7b','name':'Qwen2.5-VL 7B','estimate':'přibližně 6–7 GB','disk_required':12*1024**3,'ram_recommended':32*1024**3,
          'source':'https://ollama.com/library/qwen2.5vl','license':'Apache-2.0 (7B); ověř podmínky u zdroje'}]
_lock=threading.RLock()
_downloads={}
_owned=None


def storage():
    path=ai.root()/'models.json'
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))['directory']
    return os.environ.get('OLLAMA_MODELS') or str(Path.home()/'.ollama'/'models')


def hardware():
    from .desktop_store import root
    total=available=None
    cpu=platform.processor() or None
    if os.name=='nt':
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in ('total','available','total_page','available_page','total_virtual','available_virtual','extended')]
        value=Memory();value.length=ctypes.sizeof(value)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):total,available=value.total,value.available
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:cpu=winreg.QueryValueEx(key,'ProcessorNameString')[0]
        except OSError:pass
    else:
        try:
            values={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if len(line.split())>=2}
            total,available=values.get('MemTotal'),values.get('MemAvailable')
        except (OSError,ValueError):pass
    gpus=[]
    if executable:=shutil.which('nvidia-smi'):
        try:
            result=subprocess.run([executable,'--query-gpu=name,memory.total,memory.free,driver_version','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            if result.returncode==0:
                for row in csv.reader(io.StringIO(result.stdout)):
                    if len(row)==4:
                        gpus.append({'name':row[0].strip(),'total_bytes':int(float(row[1]))*1024**2,'available_bytes':int(float(row[2]))*1024**2,'driver':row[3].strip()})
        except (OSError,ValueError,subprocess.TimeoutExpired):pass
    disk=shutil.disk_usage(root())
    recommend='qwen2.5vl:7b' if total and total>=30*1024**3 else 'qwen2.5vl:3b'
    return {'os':platform.platform(),'cpu':cpu,'cores':os.cpu_count(),'ram_total':total,'ram_available':available,'gpus':gpus,
            'disk_free':disk.free,'disk_total':disk.total,'data_directory':str(root()),'recommended':recommend,
            'acceleration':'Ovladač NVIDIA zjištěn; skutečné využití ověří načtený model.' if gpus else 'Nelze zjistit; model může běžet na CPU.',
            'advice':'Doporučení není záruka paměti ani rychlosti. Vision, kvantizace, kontext a ostatní aplikace potřebují další paměť. Sdílená RAM není VRAM.'}


def service_status():
    from scripts.download_models import MANIFEST
    from . import main as m
    voices=[{'id':'piper:'+language,'name':'Piper · '+('čeština / Jiří' if language=='cs' else 'angličtina / Lessac'),
             'estimate':'přibližně 64 MB','disk_required':200*1024**2,'ram_recommended':1024**3,
             'source':'https://huggingface.co/rhasspy/piper-voices','license':'Podmínky hlasu jsou v ověřeném MODEL_CARD; provoz hlasu je offline.'} for language in MANIFEST]
    installed_voices=[{'language':language,'name':info['name'],'installed':all((m.MODELS/(info['name']+suffix)).is_file() for suffix in ('.onnx','.onnx.json'))} for language,info in MANIFEST.items()]
    return {'owned':_owned is not None and _owned.poll() is None,'storage':storage(),'catalog':CATALOG+voices,'voices':installed_voices,
            'downloads':[dict(row['state']) for row in _downloads.values()],
            'install_url':'https://ollama.com/download/windows'}


def set_storage(directory):
    if _owned is not None and _owned.poll() is None:raise HTTPException(409,'Před změnou úložiště zastav službu spuštěnou aplikací.')
    path=Path(directory)
    if not path.is_absolute() or not path.is_dir() or path.is_symlink():raise HTTPException(400,'Vyber existující složku modelů.')
    atomic_json(ai.root()/'models.json',{'directory':str(path.resolve())})
    return {'directory':str(path.resolve()),'message':'Platí pro Ollama spuštěnou aplikací. U externí služby změň OLLAMA_MODELS v jejím nastavení a restartuj ji; existující modely se nepřesouvají.'}


def start_service():
    global _owned
    with _lock:
        if _owned is not None and _owned.poll() is None:return service_status()
        profile=ai.load()['providers']['ollama']
        if profile['endpoint']!='http://127.0.0.1:11434':raise HTTPException(409,'Spuštění je podporované pro výchozí loopback Ollama. Vlastní službu spusť samostatně.')
        try:
            with httpx.Client(timeout=1,trust_env=False,follow_redirects=False) as client:
                if client.get(profile['endpoint']+'/api/version').status_code==200:
                    return {**service_status(),'message':'Ollama už běží externě. Aplikace ji nebude ukončovat.'}
        except httpx.HTTPError:pass
        executable=shutil.which('ollama')
        known=Path(os.environ.get('LOCALAPPDATA',''))/'Programs'/'Ollama'/'ollama.exe'
        if not executable and os.name=='nt' and known.is_file():executable=str(known)
        if not executable:raise HTTPException(409,'Ollama není nainstalovaná. Použij oficiální instalátor v Nastavení → Lokální modely.')
        model_path=Path(storage());model_path.mkdir(parents=True,exist_ok=True)
        environment={**os.environ,'OLLAMA_HOST':'127.0.0.1:11434','OLLAMA_MODELS':str(model_path),'OLLAMA_NO_CLOUD':'1'}
        _owned=subprocess.Popen([executable,'serve'],env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,start_new_session=os.name!='nt')
        return service_status()


def stop_service():
    global _owned
    with _lock:
        if _owned is not None:
            from .work_budget import _terminate
            if _owned.poll() is None:_terminate(_owned)
            _owned=None
    return service_status()


def download(model):
    if model in ('piper:en','piper:cs'):return download_voice(model.split(':')[1])
    catalog=next((row for row in CATALOG if row['id']==model),None)
    if not catalog:raise HTTPException(400,'Model není v katalogu důvěryhodných zdrojů. Další modely lze nainstalovat přímo v Ollama.')
    from . import main as m
    if any(row.get('status') not in ('done','failed') and row.get('ai')=={'provider':'ollama','model':model} for row in m.jobs.values()):
        raise HTTPException(409,'Tento model právě používá běžící úloha. Před obnovou jeho souborů ji dokonči nebo zastav.')
    folder=Path(storage())
    parent=folder
    while not parent.exists():parent=parent.parent
    if shutil.disk_usage(parent).free<catalog['disk_required']:raise HTTPException(409,'Na disku modelů není dost místa pro model a rezervu.')
    profile=ai.load()['providers']['ollama'];providers.endpoint(profile['endpoint'],'local')
    with _lock:
        if any(row['state']['status']=='downloading' for row in _downloads.values()):raise HTTPException(409,'Stahování už běží. Nejdřív ho dokonči nebo zastav.')
        identity=uuid.uuid4().hex;cancel=threading.Event()
        state={'id':identity,'model':model,'status':'downloading','percent':None,'completed':0,'total':None,'message':'Připojuji oficiální službu Ollama…'}
        _downloads[identity]={'state':state,'cancel':cancel}
    async def consume():
        async with httpx.AsyncClient(timeout=httpx.Timeout(120,connect=5),trust_env=False,follow_redirects=False) as client:
            async with client.stream('POST',profile['endpoint']+'/api/pull',json={'model':model,'stream':True},headers=providers.headers(profile,ai.credential(profile))) as response:
                if response.status_code!=200:raise providers.ProviderError('Stahování modelu bylo odmítnuto.')
                success=False
                async for line in response.aiter_lines():
                    if not line:continue
                    data=json.loads(line)
                    if data.get('error'):raise providers.ProviderError('Ollama nedokončila stahování.')
                    total=data.get('total');completed=data.get('completed',0)
                    with _lock:
                        if type(total) is int and total>0 and type(completed) is int:
                            state.update(total=total,completed=completed,percent=min(100,round(completed/total*100,1)))
                        state['message']=str(data.get('status','Stahuji…'))[:160]
                    if data.get('status')=='success':success=True
                if not success:raise providers.ProviderError('Stahování skončilo před ověřením modelu.')
    async def controlled():
        task=asyncio.create_task(consume())
        try:
            while not task.done():
                if cancel.is_set():task.cancel();raise asyncio.CancelledError()
                await asyncio.wait({task},timeout=.2)
            await task
        finally:
            if not task.done():
                task.cancel()
                try:await task
                except asyncio.CancelledError:pass
    def worker():
        try:
            asyncio.run(controlled())
            result=ai.test_provider('ollama')
            if not result['ok'] or not any(row['id']==model for row in result['models']):raise providers.ProviderError('Model po stažení nebyl ověřen.')
            with _lock:state.update(status='done',percent=100,message='Model byl stažen a ověřen službou Ollama.')
        except asyncio.CancelledError:
            with _lock:state.update(status='cancelled',message='Stažení zastaveno. Další příprava stejného modelu využije hotové části podle podpory Ollama.')
        except Exception:
            with _lock:state.update(status='failed',message='Stažení nebo ověření selhalo. Ověř síť, místo a spuštěnou Ollama; lze zkusit znovu.')
    thread=threading.Thread(target=worker,name='model-download',daemon=True)
    _downloads[identity]['thread']=thread;thread.start()
    return dict(state)


def download_voice(language):
    """Pinned official voice manifest, public CDN redirects, resumable partials."""
    from scripts.download_models import MANIFEST,verified
    from . import main as m
    info=MANIFEST[language];m.MODELS.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(m.MODELS).free<200*1024**2:raise HTTPException(409,'Pro hlas a rezervu uvolni alespoň 200 MB v datovém adresáři.')
    identity=uuid.uuid4().hex;cancel=threading.Event()
    state={'id':identity,'model':'piper:'+language,'status':'downloading','percent':0,'completed':0,'total':None,'message':'Stahuji oficiální hlas Piper…'}
    with _lock:
        if any(row['state']['status']=='downloading' for row in _downloads.values()):raise HTTPException(409,'Nejdřív dokonči nebo pozastav stahování.')
        _downloads[identity]={'state':state,'cancel':cancel}
    async def consume():
        total=sum(size for size,_ in info['files'].values());done=0
        # Public model downloads contain no credentials and may use the official
        # host's CDN. Exact byte lengths and publisher digests must still match.
        async with httpx.AsyncClient(timeout=60,trust_env=False,follow_redirects=True) as client:
            for suffix,(size,digest) in info['files'].items():
                remote=suffix if suffix=='MODEL_CARD' else info['name']+suffix
                target=m.MODELS/(info['name']+'.MODEL_CARD' if suffix=='MODEL_CARD' else remote)
                if verified(target,size,digest):done+=size;continue
                temporary=target.with_suffix(target.suffix+'.part')
                if temporary.exists() and temporary.stat().st_size>=size:temporary.unlink()
                offset=temporary.stat().st_size if temporary.exists() else 0
                url='https://huggingface.co/rhasspy/piper-voices/resolve/main/'+info['path']+remote
                async with client.stream('GET',url,headers={'Range':f'bytes={offset}-'} if offset else {}) as response:
                    if response.status_code not in (200,206):raise providers.ProviderError('Zdroj hlasu není dostupný.')
                    append=offset>0 and response.status_code==206 and response.headers.get('content-range','').startswith(f'bytes {offset}-')
                    written=offset if append else 0
                    with temporary.open('ab' if append else 'wb') as output:
                        async for chunk in response.aiter_bytes(1024**2):
                            written+=len(chunk)
                            if written>size:raise providers.ProviderError('Hlas překročil ověřenou velikost.')
                            output.write(chunk)
                            with _lock:state.update(completed=done+written,total=total,percent=round((done+written)/total*100,1))
                if not verified(temporary,size,digest):raise providers.ProviderError('Kontrolní součet hlasu nesouhlasí.')
                temporary.replace(target);done+=size
    async def controlled():
        task=asyncio.create_task(consume())
        try:
            while not task.done():
                if cancel.is_set():task.cancel();raise asyncio.CancelledError()
                await asyncio.wait({task},timeout=.2)
            await task
        finally:
            if not task.done():
                task.cancel()
                try:await task
                except asyncio.CancelledError:pass
    def worker():
        try:
            asyncio.run(controlled())
            with _lock:state.update(status='done',percent=100,message='Hlas byl ověřen podle manifestu. V editoru vyber Piper pro práci offline.')
        except asyncio.CancelledError:
            with _lock:state.update(status='cancelled',message='Hlas pozastaven. Další stažení zkusí navázat přes HTTP Range.')
        except Exception:
            with _lock:state.update(status='failed',message='Hlas se nepodařilo stáhnout nebo ověřit. Částečné soubory nejsou vydávané za hotový hlas.')
    thread=threading.Thread(target=worker,name='voice-download',daemon=True)
    _downloads[identity]['thread']=thread;thread.start()
    return dict(state)


def cancel_download(identity):
    with _lock:
        row=_downloads.get(identity)
        if not row:raise HTTPException(404,'Stahování nebylo nalezeno.')
        row['cancel'].set()
        return dict(row['state'])


def delete(model,confirmation):
    from . import main as m
    if model!=confirmation:raise HTTPException(400,'Potvrzení názvu modelu nesouhlasí.')
    if any(row['state']['status']=='downloading' and row['state']['model']==model for row in _downloads.values()):raise HTTPException(409,'Nejdřív pozastav stahování tohoto modelu.')
    if any(row.get('status') not in ('done','failed') for row in m.jobs.values()):raise HTTPException(409,'Před odstraněním dokonči nebo zastav běžící úlohy.')
    if model in ('piper:en','piper:cs'):
        from scripts.download_models import MANIFEST
        info=MANIFEST[model.split(':')[1]]
        m.voices.pop(model.split(':')[1],None)
        for suffix in ('.onnx','.onnx.json','.MODEL_CARD'):
            target=m.MODELS/(info['name']+suffix)
            if target.is_symlink():raise HTTPException(400,'Úložiště hlasu obsahuje nepodporovaný odkaz.')
        for suffix in ('.onnx','.onnx.json','.MODEL_CARD'):(m.MODELS/(info['name']+suffix)).unlink(missing_ok=True)
        return {'deleted':True}
    profile=ai.load()['providers']['ollama']
    known=providers.discover(profile,ai.credential(profile))
    if not any(row['id']==model for row in known):raise HTTPException(404,'Nainstalovaný model nebyl nalezen.')
    try:
        with httpx.Client(timeout=30,trust_env=False,follow_redirects=False) as client:
            response=client.request('DELETE',profile['endpoint']+'/api/delete',json={'model':model},headers=providers.headers(profile,ai.credential(profile)))
            if response.status_code not in (200,204):raise HTTPException(502,'Ollama model neodstranila.')
    except httpx.HTTPError:raise HTTPException(502,'Ollama neodpovídá.') from None
    return ai.test_provider('ollama')


def shutdown():
    for identity,row in list(_downloads.items()):row['cancel'].set()
    for row in list(_downloads.values()):row['thread'].join(timeout=3)
    stop_service()
