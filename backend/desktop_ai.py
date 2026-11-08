"""Persistent desktop AI configuration and immutable per-job selections."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
import copy
import json
import os
import threading
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from . import ai_providers as providers
from .desktop_secrets import Vault,atomic_json,SecretStorageError

router=APIRouter(prefix='/api/desktop/ai')
_lock=threading.RLock()
_selection=ContextVar('desktop_ai_selection',default=None)


def enabled():return os.environ.get('RANK_DESKTOP_MODE')=='1'


def root():
    from . import main as m
    return m.DATA/'private'/'desktop'


def vault():return Vault(root())


def credential_scope(profile):
    """Keys belong to a provider AND an authority, not a mutable URL field."""
    url=urlsplit(profile['endpoint'])
    host=url.hostname or ''
    if ':' in host:host='['+host+']'
    port=url.port
    origin=url.scheme+'://'+host+((':'+str(port)) if port and port!={'https':443,'http':80}.get(url.scheme) else '')
    return profile['id']+'@'+origin


def credential(profile):return vault().get(credential_scope(profile))


def defaults():
    return {'version':1,'mode':'local','wizard_complete':False,
            'active':{'provider':'ollama','model':''},
            'providers':{identity:{'id':identity,'enabled':identity=='ollama','endpoint':row['url'],
                                  'models':[],'vision_overrides':[],'checked_at':None,'error':None}
                         for identity,row in providers.PROVIDERS.items()}}


def load():
    with _lock:
        path=root()/'ai.json'
        if not path.exists():return defaults()
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            if data.get('version')!=1 or not isinstance(data.get('providers'),dict):raise ValueError()
            return data
        except (ValueError,OSError,AttributeError):
            raise providers.ProviderError('Konfigurace AI je nečitelná nebo z novější verze. Nebyla přepsána.') from None


def save(data):atomic_json(root()/'ai.json',data)


def public_config():
    data=load()
    for identity,profile in data['providers'].items():
        profile.update(name=providers.PROVIDERS[identity]['name'],kind=providers.PROVIDERS[identity]['kind'],has_key=vault().contains(credential_scope(profile)))
    data['secure_storage']='Windows DPAPI' if os.name=='nt' else 'Pouze paměť: vývoj mimo Windows neukládá API klíče na disk.'
    return data


def snapshot():
    with _lock:return _snapshot()


def _snapshot():
    config=load();identity=config['active']['provider'];model=config['active']['model'];profile=config['providers'].get(identity)
    if not profile or not profile['enabled'] or not model:return {}
    kind=providers.PROVIDERS[identity]['kind']
    if config['mode']!='hybrid' and kind!=config['mode']:return {}
    info=next((row for row in profile['models'] if row['id']==model),None)
    if not info:return {}
    key=credential(profile)
    if kind=='cloud' and not key:return {}
    return {'profile':copy.deepcopy(profile),'model':model,'key':key,
            'vision':info.get('vision') is True or model in profile.get('vision_overrides',[]),
            'context':8192 if model!='qwen2.5vl:3b' else 16384}


def selected():
    value=_selection.get()
    return value if value is not None else snapshot()


class DesktopExecutor(ThreadPoolExecutor):
    def submit(self,fn,/,*args,**kwargs):
        selection=snapshot()
        # An explicitly technical/free operation must never spend a configured
        # cloud key on incidental overlay cleanup or commentary.
        mode=next((getattr(arg,'mode') for arg in args[1:] if hasattr(arg,'mode')),None)
        if mode=='free' and selection and providers.PROVIDERS[selection['profile']['id']]['kind']=='cloud':selection={}
        from . import main as m
        if selection and args and isinstance(args[0],str):
            with m.job_lock:
                if args[0] in m.jobs:m.jobs[args[0]]['ai']={'provider':selection['profile']['id'],'model':selection['model']}
        def invoke():
            token=_selection.set(selection)
            from . import main as m,work_budget as work
            identity=args[0] if args and isinstance(args[0],str) and args[0] in m.jobs else None
            budget=work.reserve(identity,3600) if identity else None
            if budget:budget.label=lambda text:m.set_job(identity,message=text)
            work_token=work._active.set(budget)
            try:return fn(*args,**kwargs)
            finally:
                work._active.reset(work_token);_selection.reset(token)
                if identity:
                    with work._lock:work._controls.pop(identity,None)
        return super().submit(invoke)


def require_ready(vision=False):
    selection=selected()
    if not selection:raise providers.ProviderError('V Nastavení → AI modely ověř poskytovatele a vyber dostupný model. Cloud potřebuje vlastní klíč.')
    if vision and not selection.get('vision'):
        raise providers.ProviderError('Tento model nemá ověřenou podporu obrázků. DeepSeek může psát text; pro výběr videa zvol vizuální model.')
    return selection


def overlay_review_allowed():
    selection=selected()
    if not selection:return False
    # A standalone OCR/manual detector is free by default. Cloud overlays are
    # part of an explicit AI selection/cleanup job with a captured selection.
    return providers.PROVIDERS[selection['profile']['id']]['kind']=='local' or _selection.get() is not None


def vision_status():
    try:selection=selected();config=load()
    except (providers.ProviderError,SecretStorageError) as error:
        return {'supported':True,'ready':False,'model':'Nelze načíst','message':str(error)}
    return {'supported':True,'ready':bool(selection and selection.get('vision')),
            'model':config['active']['model'] or 'Nevybrán','provider':config['active']['provider'],
            'message':('Vybraný model: '+config['active']['model']+'. Poslední ověření je v Nastavení → AI modely.' if selection.get('vision') else 'Vybraný model '+config['active']['model']+' nemá ověřenou podporu obrázků. Pro hledání momentů vyber vizuální model v Nastavení → AI modely.') if selection else
                      'Otevři Nastavení → AI modely a ověř připojení. Lokální provoz je zdarma.'}


def request(prompt,evidence,tokens):
    selection=require_ready(vision=any(b.get('type')=='image_url' for b in evidence))
    return providers.generate(selection,[{'role':'system','content':prompt},{'role':'user','content':evidence}],tokens)


def legacy_request(payload,responses=False):
    selection=require_ready()
    if responses:
        if selection['profile']['id']!='openai':
            raise providers.ProviderError('Tato operace potřebuje OpenAI webové vyhledávání. Zvolený poskytovatel nebyl změněn; běžné hledání klipů funguje bez něj.')
        from . import work_budget as work
        try:
            body={**payload,'model':selection['model']}
            response=work.post_json(selection['profile']['endpoint']+'/responses',headers=providers.headers(selection['profile'],selection['key']),payload=body,seconds=120,local=True)
            data=providers.safe_response(response)
            text=''.join(c.get('text','') for row in data.get('output',[]) for c in row.get('content',[]) if c.get('type')=='output_text')
            import re
            result=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip()))
            if not isinstance(result,dict):raise ValueError()
            citations={source['url'] for row in data.get('output',[]) for source in row.get('action',{}).get('sources',[]) if isinstance(source.get('url'),str)}
            for row in data.get('output',[]):
                for content in row.get('content',[]):
                    citations.update(a['url'] for a in content.get('annotations',[]) if a.get('type')=='url_citation' and isinstance(a.get('url'),str))
            result['_evidence_urls']=sorted(citations)
            return result
        except (ValueError,KeyError,TypeError) as error:
            if isinstance(error,providers.ProviderError):raise
            raise providers.ProviderError('Webové vyhledávání AI nevrátilo platná data.') from None
    return providers.generate(selection,payload.get('messages',[]),min(payload.get('max_tokens',1800),4096))


class ProviderPatch(BaseModel):
    enabled:bool
    endpoint:str=Field(max_length=1000)
    vision_overrides:list[str]=Field(default_factory=list,max_length=100)


class ConfigPatch(BaseModel):
    mode:Literal['local','cloud','hybrid']
    provider:str=Field(max_length=40)
    model:str=Field(default='',max_length=200)
    wizard_complete:bool|None=None
    providers:dict[str,ProviderPatch]=Field(default_factory=dict,max_length=10)


@router.get('/config')
def get_config():return public_config()


@router.post('/config')
def configure(body:ConfigPatch):
    with _lock:
        data=load()
        if body.provider not in providers.PROVIDERS:raise HTTPException(400,'Neznámý poskytovatel.')
        for identity,patch in body.providers.items():
            if identity not in providers.PROVIDERS:raise HTTPException(400,'Neznámý poskytovatel.')
            definition=providers.PROVIDERS[identity]
            try:url=providers.endpoint(patch.endpoint,definition['kind']) if patch.endpoint else ''
            except providers.ProviderError as error:raise HTTPException(400,str(error)) from None
            if definition['kind']=='cloud' and identity!='custom' and url!=definition['url']:
                raise HTTPException(400,'Pro jinou cloudovou adresu použij Vlastní kompatibilní API. Klíč tohoto poskytovatele zůstává u jeho oficiálního endpointu.')
            profile=data['providers'][identity]
            if url!=profile['endpoint']:profile.update(models=[],checked_at=None,error=None)
            known={row['id'] for row in profile['models']}
            unknown={row['id'] for row in profile['models'] if row.get('vision') is None}
            if not set(patch.vision_overrides)<=unknown:raise HTTPException(400,'Schopnost lze potvrdit pouze u objeveného modelu s neznámými schopnostmi.')
            profile.update(enabled=patch.enabled,endpoint=url,vision_overrides=patch.vision_overrides)
        profile=data['providers'][body.provider]
        if body.model and not any(row['id']==body.model for row in profile['models']) and data['active']!={'provider':body.provider,'model':body.model}:
            raise HTTPException(400,'Model nebyl ověřen u zvoleného poskytovatele. Nejdřív načti seznam modelů.')
        if body.mode!='hybrid' and providers.PROVIDERS[body.provider]['kind']!=body.mode:
            raise HTTPException(400,'Poskytovatel neodpovídá zvolenému režimu.')
        data.update(mode=body.mode,active={'provider':body.provider,'model':body.model})
        if body.wizard_complete is not None:data['wizard_complete']=body.wizard_complete
        save(data)
    return public_config()


class KeyBody(BaseModel):
    key:str=Field(max_length=4096,repr=False)


@router.post('/providers/{identity}/key')
def set_key(identity:str,body:KeyBody):
    if identity not in providers.PROVIDERS:raise HTTPException(404,'Neznámý poskytovatel.')
    value=body.key.strip()
    if any(ord(c)<32 or ord(c)>126 for c in value):raise HTTPException(400,'Klíč obsahuje znaky, které nejsou platné pro API autentizaci.')
    with _lock:
        data=load();profile=data['providers'][identity]
        if not profile['endpoint']:raise HTTPException(400,'Nejdřív ulož adresu poskytovatele, ke které klíč patří.')
        vault().set(credential_scope(profile),value)
        profile.update(models=[],checked_at=None,error=None);save(data)
    return {'stored':bool(value),'persistent':os.name=='nt'}


@router.post('/providers/{identity}/test')
def test_provider(identity:str):
    if identity not in providers.PROVIDERS:raise HTTPException(404,'Neznámý poskytovatel.')
    with _lock:
        profile=copy.deepcopy(load()['providers'][identity]);key=credential(profile)
    try:
        if not profile['endpoint']:raise providers.ProviderError('Nejdřív nastav endpoint.')
        if providers.PROVIDERS[identity]['kind']=='cloud' and not key:raise providers.ProviderError('Nejdřív ulož API klíč.')
        rows=providers.discover(profile,key)
        error=None
    except providers.ProviderError as reason:
        rows=[];error=str(reason)
    except (TypeError,AttributeError):
        rows=[];error='Připojení nebo seznam modelů není dostupný. Ověř službu, adresu a klíč; údaje nebyly předány jiné službě.'
    with _lock:
        data=load();current=data['providers'][identity]
        if current['endpoint']!=profile['endpoint']:raise HTTPException(409,'Adresa se během ověřování změnila. Ověř ji znovu.')
        current.update(models=rows,checked_at=time.time(),error=error)
        current['vision_overrides']=[model for model in current.get('vision_overrides',[]) if any(row['id']==model and row.get('vision') is None for row in rows)]
        save(data)
    return {'ok':error is None,'models':rows,'error':error,'config':public_config()}


@router.post('/detect')
def detect_local():
    results=[]
    # Probe only known loopback services, never a LAN scan or cloud provider.
    for identity in ('ollama','lmstudio','llamacpp','local'):
        result=test_provider(identity)
        results.append({'provider':identity,'ok':result['ok'],'models':result['models']})
    return {'services':results,'config':public_config()}


class PromptBody(BaseModel):
    prompt:str=Field(min_length=1,max_length=12000)


@router.post('/generate',status_code=202)
def generate_text(body:PromptBody):
    from . import main as m,work_budget as work
    import uuid
    try:require_ready()
    except providers.ProviderError as error:raise HTTPException(409,str(error)) from None
    identity=uuid.uuid4().hex;work.reserve(identity,240)
    with m.job_lock:m.jobs[identity]={'id':identity,'status':'queued','kind':'desktop-ai','progress':0,'message':'Připravuji odpověď AI…'}
    @work.limited_discovery
    def run(job_id):
        try:
            m.set_job(job_id,status='working',progress=10,message='Vybraný model píše odpověď…')
            result=legacy_request({'messages':[{'role':'system','content':'Return JSON {"text":"your helpful answer"}.'},{'role':'user','content':body.prompt}],'max_tokens':1800})
            if not isinstance(result.get('text'),str) or len(result['text'])>20000:raise providers.ProviderError('Model nevrátil text v požadovaném formátu.')
            m.set_job(job_id,status='done',progress=100,message='Hotovo.',result=result,usage=getattr(work.current(),'ai_usage',None))
        except work.WorkStopped:raise
        except providers.ProviderError as reason:m.set_job(job_id,status='failed',progress=100,message=str(reason))
        except Exception:m.set_job(job_id,status='failed',progress=100,message='AI požadavek selhal. Ověř poskytovatele, model a jeho limity.')
    m.executor.submit(run,identity)
    return dict(m.jobs[identity])
