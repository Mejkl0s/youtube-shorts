"""Ollama vision on this computer only. No cloud endpoints or API keys."""
import json
import os
import re
import threading
import time
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import work_budget as work

MODEL = 'qwen2.5vl:7b'
MODEL_OPTIONS = ('qwen2.5vl:3b','qwen2.5vl:7b')
CONTEXT = {'qwen2.5vl:3b':16384,'qwen2.5vl:7b':8192}
BASE = 'http://127.0.0.1:11434'
_status_cache = None
_status_lock = threading.Lock()
router=APIRouter(prefix='/api/local-vision')
_setup_process=None
_setup_lock=threading.Lock()


class LocalVisionError(ValueError):
    pass


def supported():
    return os.environ.get('RANK_LOCAL_MODE') == '1' and os.environ.get('STUDIO_PUBLIC') != '1'


def model_path():
    from . import main as m
    return m.DATA/'private'/'local-vision.json'


def selected_model():
    try:
        data=json.loads(model_path().read_text(encoding='utf-8'))
        value=data.get('model') if isinstance(data,dict) else None
        return value if value in MODEL_OPTIONS else MODEL
    except (OSError,ValueError):
        return MODEL


def status(refresh=False):
    global _status_cache
    if os.environ.get('RANK_DESKTOP_MODE')=='1':
        from .desktop_ai import vision_status
        return vision_status()
    model=selected_model()
    if not supported():
        return {'supported':False,'ready':False,'model':model,'message':'AI zdarma běží na tvém PC, nikoli na bezplatném Renderu.'}
    with _status_lock:
        if not refresh and _status_cache and _status_cache[1]['model']==model and time.monotonic()-_status_cache[0] < 5:
            return dict(_status_cache[1])
    result={'supported':True,'ready':False,'model':model,'models':list(MODEL_OPTIONS),'context_tokens':CONTEXT[model],
            'message':f'Připrav vybraný model {model}. Poprvé se stáhne několik GB.'}
    try:
        with httpx.Client(timeout=1,trust_env=False,follow_redirects=False) as client:
            response=client.get(BASE+'/api/tags')
            response.raise_for_status()
            listing=response.json()
            models=listing.get('models',[]) if isinstance(listing,dict) else []
            if not isinstance(models,list):
                models=[]
            # Cloud aliases are not accepted: require an actual local model file.
            installed=any(isinstance(row,dict) and row.get('name')==model and type(row.get('size')) is int and row['size']>10_000_000
                          and re.fullmatch(r'[a-f0-9]{64}',str(row.get('digest',''))) for row in models)
            if installed:
                info=client.post(BASE+'/api/show',json={'model':model})
                info.raise_for_status()
                data=info.json()
                if (isinstance(data,dict) and isinstance(data.get('capabilities'),list) and 'vision' in data['capabilities']
                        and not data.get('remote_host') and not data.get('remote_model')):
                    result.update(ready=True,message=f'Model {model} je uložený na tomto PC. Výběr nepoužívá placené API.')
                    # Optional read-only residency after inference: installed
                    # weights alone do not prove the model fits entirely in VRAM.
                    running=client.get(BASE+'/api/ps')
                    if running.status_code==200:
                        data=running.json()
                        loaded=data.get('models',[]) if isinstance(data,dict) else []
                        for row in loaded if isinstance(loaded,list) else []:
                            if (isinstance(row,dict) and row.get('name')==model and type(row.get('size')) is int
                                    and type(row.get('size_vram')) is int and 0<=row['size_vram']<=row['size'] and row['size']>0):
                                result['memory']={'total_bytes':row['size'],'gpu_bytes':row['size_vram']}
                                break
    except (httpx.HTTPError,ValueError,TypeError):
        pass
    with _status_lock:
        _status_cache=(time.monotonic(),dict(result))
    return result


def require_ready():
    state=status()
    if not state['ready']:
        raise LocalVisionError(state['message'])


class ModelChoice(BaseModel):
    model:Literal['qwen2.5vl:3b','qwen2.5vl:7b']


@router.post('/model')
def choose_model(body:ModelChoice):
    from . import main as m
    global _status_cache
    if os.environ.get('RANK_DESKTOP_MODE')=='1':raise HTTPException(409,'V desktopu vyber model přes horní lištu nebo Nastavení → AI modely.')
    if not supported():
        raise HTTPException(409,'Model vyber ve studiu na svém PC.')
    with _setup_lock,m.job_lock:
        if _setup_process is not None and _setup_process.poll() is None:
            raise HTTPException(409,'Nejdřív zavři okno přípravy modelu, potom změň model.')
        if any(j.get('status') in ('queued','rendering','searching','working') for j in m.jobs.values()):
            raise HTTPException(409,'Model můžeš změnit po dokončení nebo zastavení aktuálního úkolu.')
        path=model_path();path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps({'model':body.model}),encoding='utf-8')
            temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)
        with _status_lock:_status_cache=None
    return get_status()


@router.get('/status')
def get_status():
    return {**status(refresh=True),'setup_running':_setup_process is not None and _setup_process.poll() is None}


@router.post('/setup')
def start_setup():
    """User-clicked preparation: a fixed, visible installer on their own PC."""
    from . import main as m
    import subprocess
    global _setup_process
    if os.environ.get('RANK_DESKTOP_MODE')=='1':raise HTTPException(409,'Použij Nastavení → Lokální modely. Desktop nevyžaduje příkazové okno.')
    if not supported():
        raise HTTPException(409,'Přípravu spusť ve studiu na svém PC na adrese 127.0.0.1:8765.')
    if os.name!='nt':
        raise HTTPException(409,f'Na tomto systému nainstaluj Ollama, spusť ollama serve a potom ollama pull {selected_model()}.')
    with _setup_lock:
        if _setup_process is not None and _setup_process.poll() is None:
            return {'started':True,'message':'Příprava už běží v samostatném okně.'}
        # No user-supplied shell text, model name, executable or arguments.
        script=m.ROOT/'scripts'/'setup_local_vision.ps1'
        try:
            _setup_process=subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Model',selected_model()],
                                            cwd=m.ROOT,creationflags=subprocess.CREATE_NEW_CONSOLE)
        except OSError:
            raise HTTPException(409,'Okno přípravy se nepodařilo otevřít. Spusť scripts/setup_local_vision.ps1 ze složky aplikace.') from None
    return {'started':True,'message':'Otevřelo se okno přípravy. Poprvé nainstaluje Ollama a stáhne několikaGB model. Průběh je v tomto okně.'}


def _call(prompt,evidence,tokens):
    if os.environ.get('RANK_DESKTOP_MODE')=='1':
        from .desktop_ai import request
        return request(prompt,evidence,tokens)
    require_ready()
    model=selected_model()
    text=[]
    images=[]
    for block in evidence:
        if block.get('type')=='text':
            text.append(block['text'])
        elif block.get('type')=='image_url':
            image=block.get('image_url',{}).get('url','')
            if not image.startswith('data:image/jpeg;base64,'):
                raise LocalVisionError('Lokální AI přijímá jen připravené snímky videa.')
            images.append(image.split(',',1)[1])
    payload={'model':model,'stream':False,'format':'json','keep_alive':'5m',
             'messages':[{'role':'system','content':prompt},
                         {'role':'user','content':'\n'.join(text),'images':images}],
             'options':{'temperature':0,'num_ctx':CONTEXT[model],'num_predict':tokens}}
    try:
        response=work.post_json(BASE+'/api/chat',headers={},payload=payload,seconds=240,local=True)
        response.raise_for_status()
        data=response.json()
        if not isinstance(data,dict):
            raise ValueError()
        if data.get('done_reason')=='length':
            raise LocalVisionError('Lokální model nedokončil odpověď. Zkus kratší scénu.')
        message=data.get('message')
        if not isinstance(message,dict) or not isinstance(message.get('content'),str):
            raise ValueError()
        content=message['content']
        content=re.sub(r'^```(?:json)?\s*|\s*```$','',content.strip())
        result=json.loads(content)
        if not isinstance(result,dict):
            raise ValueError()
        return result
    except work.WorkStopped:
        raise
    except LocalVisionError:
        raise
    except (httpx.HTTPError,ValueError,TypeError):
        raise LocalVisionError('Lokální model nevrátil platný výsledek. Zkontroluj okno Ollama a dostupnou paměť; placené API se nepoužilo.') from None


def request(prompt,evidence,tokens):
    if 'FINAL REVIEW' not in prompt:
        work.stage('AI popisuje děj aktuálního výřezu…' if 'RANK NOTE REVIEW' in prompt else 'AI na tvém PC hledá rušivé překryvy…' if 'OVERLAY REVIEW' in prompt else 'AI na tvém PC hledá hlavní momenty v obrazu…')
        return _call(prompt,evidence,min(tokens,1800))
    # A small local VLM must not receive dozens of full-resolution sheets in
    # one context. Review each nominated scene independently, keeping all its
    # detailed frames, and compare the returned scores on the server.
    groups=[]
    for block in evidence:
        if block.get('type')=='text':
            groups.append([block])
        elif groups:
            groups[-1].append(block)
    combined=[]
    for index,group in enumerate(groups):
        work.stage(f'Lokální AI posuzuje děj a pointu {index+1}/{len(groups)}…')
        result=_call(prompt+' Review ONLY the scene provided in this request. Return zero or one accepted moment. '
                     'Give the score using the same absolute 0–100 clarity/action scale; do not invent other scenes.',group,min(tokens,1200))
        moments=result.get('moments')
        if not isinstance(moments,list) or len(moments)>1:
            raise LocalVisionError('Lokální AI nevrátila platné posouzení jedné scény.')
        combined.extend(moments)
    return {'moments':combined}
