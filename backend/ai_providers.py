"""Provider-specific transports. Discovery is read-only; inference never falls back."""
import base64
import json
import ipaddress
import re
from urllib.parse import urlsplit

import httpx

from . import work_budget as work

PROVIDERS={
    'ollama':{'name':'Ollama','kind':'local','url':'http://127.0.0.1:11434','adapter':'ollama'},
    'lmstudio':{'name':'LM Studio','kind':'local','url':'http://127.0.0.1:1234/v1','adapter':'compatible'},
    'llamacpp':{'name':'llama.cpp','kind':'local','url':'http://127.0.0.1:8080/v1','adapter':'compatible'},
    'local':{'name':'Vlastní lokální API','kind':'local','url':'http://127.0.0.1:8081/v1','adapter':'compatible'},
    'openai':{'name':'OpenAI','kind':'cloud','url':'https://api.openai.com/v1','adapter':'openai'},
    'anthropic':{'name':'Anthropic Claude','kind':'cloud','url':'https://api.anthropic.com/v1','adapter':'anthropic'},
    'gemini':{'name':'Google Gemini','kind':'cloud','url':'https://generativelanguage.googleapis.com/v1beta','adapter':'gemini'},
    'deepseek':{'name':'DeepSeek','kind':'cloud','url':'https://api.deepseek.com','adapter':'compatible'},
    'openrouter':{'name':'OpenRouter','kind':'cloud','url':'https://openrouter.ai/api/v1','adapter':'compatible'},
    'custom':{'name':'Vlastní kompatibilní API','kind':'cloud','url':'','adapter':'compatible'},
}


class ProviderError(ValueError):pass


def endpoint(value,kind):
    try:
        url=urlsplit(value)
        if (not url.hostname or url.username or url.password or url.query or url.fragment
                or '\\' in value or any(ord(c)<33 for c in value) or url.port==0):raise ValueError()
        if kind=='local':
            if url.hostname not in ('localhost','127.0.0.1','::1') or url.scheme not in ('http','https'):raise ValueError()
        else:
            if url.scheme!='https' or url.hostname in ('localhost','127.0.0.1','::1'):raise ValueError()
            try:address=ipaddress.ip_address(url.hostname)
            except ValueError:address=None
            if address and not address.is_global:raise ValueError()
        return value.rstrip('/')
    except ValueError:
        raise ProviderError('Lokální adresa musí být loopback HTTP(S); cloudová adresa HTTPS bez hesla, parametrů a přesměrování.') from None


def headers(profile,key):
    adapter=PROVIDERS[profile['id']]['adapter']
    if adapter=='anthropic':return {'x-api-key':key,'anthropic-version':'2023-06-01'}
    if adapter=='gemini':return {'x-goog-api-key':key}
    return {'Authorization':'Bearer '+key} if key else {}


def safe_response(response):
    if response.status_code>=300:
        descriptions={401:'Neplatný API klíč.',403:'Poskytovatel odmítl přístup.',404:'Model nebo endpoint není dostupný.',
                      429:'Limit poskytovatele nebo kredit byl vyčerpán.',400:'Model nepodporuje požadovaný formát nebo schopnost.'}
        raise ProviderError(f'AI vrátila HTTP {response.status_code}. '+descriptions.get(response.status_code,'Služba není dostupná.'))
    try:return response.json()
    except ValueError:raise ProviderError('AI nevrátila čitelnou JSON odpověď.') from None


def read(profile,key,path):
    url=endpoint(profile['endpoint'],PROVIDERS[profile['id']]['kind'])+path
    # Only safe GET discovery is retried, never billable POST inference.
    for attempt in range(2):
        try:
            with httpx.Client(timeout=8,trust_env=False,follow_redirects=False) as client:
                response=client.get(url,headers=headers(profile,key))
                if response.status_code in (502,503,504) and attempt==0:continue
                return safe_response(response)
        except (httpx.ConnectError,httpx.TimeoutException):
            if attempt:raise ProviderError('AI server neodpovídá. Ověř adresu a spuštění služby.') from None
        except httpx.HTTPError:raise ProviderError('Připojení k AI selhalo; ověř HTTPS certifikát a adresu.') from None


def model_info(profile,row):
    identity=str(row.get('id') or row.get('name') or '')
    if profile['id']=='gemini':identity=identity.removeprefix('models/')
    if not identity or len(identity)>200 or not re.fullmatch(r'[\w./:+-]+',identity):return None
    vision=None
    caps=row.get('capabilities',{})
    if isinstance(caps,list):vision='vision' in caps
    elif isinstance(caps,dict) and isinstance(caps.get('vision'),bool):vision=caps['vision']
    provider=profile['id']
    if provider=='deepseek' and identity in ('deepseek-chat','deepseek-reasoner'):vision=False
    if provider=='openai':
        known=('gpt-4o','gpt-4o-mini','gpt-4.1','gpt-4.1-mini','gpt-4.1-nano','gpt-5','gpt-5-mini','gpt-5-nano','o3','o4-mini','o1')
        if any(identity==base or identity.startswith(base+'-20') for base in known):vision=True
        elif identity.startswith(('gpt-3.5','gpt-4-','text-','tts-','whisper-','dall-e','embedding')):vision=False
    if provider=='anthropic' and identity.startswith(('claude-3','claude-sonnet-4','claude-opus-4','claude-haiku-4')):vision=True
    if provider=='gemini' and identity.startswith(('gemini-1.5','gemini-2.')):vision='generateContent' in row.get('supportedGenerationMethods',[])
    if provider=='openrouter':vision='image' in row.get('architecture',{}).get('input_modalities',[])
    if row.get('type')=='vlm':vision=True
    if row.get('type') in ('llm','embeddings'):vision=False
    return {'id':identity,'name':str(row.get('displayName') or row.get('name') or identity)[:200],
            'vision':vision,'web_search':provider=='openai','size_bytes':row.get('size') if type(row.get('size')) is int else None,
            'context':row.get('context_length') or row.get('inputTokenLimit'),
            'pricing':row.get('pricing') if provider=='openrouter' else None}


def discover(profile,key):
    provider=profile['id']
    if provider=='ollama':
        rows=read(profile,key,'/api/tags').get('models',[])
        if isinstance(rows,list):rows=[row for row in rows if isinstance(row,dict) and re.fullmatch('[a-f0-9]{64}',str(row.get('digest','')))]
    elif provider=='gemini':
        rows=[];token=''
        # Limit pagination rather than accepting an unbounded remote list.
        for _ in range(10):
            from urllib.parse import quote
            data=read(profile,key,'/models?pageSize=100'+('&pageToken='+quote(token,safe='') if token else ''))
            rows.extend(data.get('models',[]));token=data.get('nextPageToken','')
            if not token:break
    elif provider=='anthropic':
        rows=[];after=''
        for _ in range(10):
            from urllib.parse import quote
            data=read(profile,key,'/models?limit=100'+('&after_id='+quote(after,safe='') if after else ''))
            rows.extend(data.get('data',[]))
            if not data.get('has_more'):break
            after=data.get('last_id','')
            if not after:break
    else:
        rows=read(profile,key,'/models').get('data',[])
    if not isinstance(rows,list):raise ProviderError('Server nevrátil seznam modelů.')
    result=[info for row in rows[:2000] if isinstance(row,dict) and (info:=model_info(profile,row))]
    # Ollama show is authoritative for vision and rejects cloud aliases.
    if provider=='ollama':
        for info in result:
            with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
                try:
                    data=safe_response(client.post(profile['endpoint']+'/api/show',headers=headers(profile,key),json={'model':info['id']}))
                    info['vision']='vision' in data.get('capabilities',[])
                    info['remote']=bool(data.get('remote_host') or data.get('remote_model'))
                except (httpx.HTTPError,ProviderError):info['vision']=None;info['remote']=True
        result=[info for info in result if not info.get('remote') and (info.get('size_bytes') or 0)>0]
    return result


def image_parts(content):
    blocks=content if isinstance(content,list) else [{'type':'text','text':str(content)}]
    result=[]
    for item in blocks:
        if item.get('type')=='text':result.append(('text',str(item.get('text',''))))
        elif item.get('type')=='image_url':
            uri=item.get('image_url',{}).get('url','')
            match=re.fullmatch(r'data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\r\n]+)',uri)
            if not match:raise ProviderError('AI přijímá pouze připravené obrazové snímky, ne cizí URL.')
            result.append(('image',{'mime':match[1],'data':match[2]}))
    return result


def prepare(selection,messages,tokens,stream=False):
    profile=selection['profile'];model=selection['model'];adapter=PROVIDERS[profile['id']]['adapter']
    has_images=any(kind=='image' for message in messages for kind,_ in image_parts(message.get('content','')))
    if has_images and not selection.get('vision'):
        raise ProviderError('Vybraný model nemá ověřenou podporu obrázků. Pro střih vyber vizuální model, například nainstalovaný Qwen2.5-VL v Ollama. Textové operace zůstávají dostupné.')
    system='\n'.join(str(m['content']) for m in messages if m.get('role')=='system')
    if adapter=='ollama':
        converted=[]
        for message in messages:
            parts=image_parts(message.get('content',''))
            converted.append({'role':message['role'],'content':'\n'.join(value for kind,value in parts if kind=='text'),
                              'images':[value['data'] for kind,value in parts if kind=='image']})
        return '/api/chat',{'model':model,'messages':converted,'format':'json','stream':stream,'keep_alive':'5m',
                            'options':{'temperature':0,'num_ctx':selection.get('context',8192),'num_predict':tokens}}
    if adapter=='anthropic':
        converted=[]
        for message in messages:
            if message.get('role')=='system':continue
            blocks=[{'type':'text','text':value} if kind=='text' else
                    {'type':'image','source':{'type':'base64','media_type':value['mime'],'data':value['data']}}
                    for kind,value in image_parts(message.get('content',''))]
            converted.append({'role':message['role'],'content':blocks})
        return '/messages',{'model':model,'system':system+'\nReturn valid JSON.','messages':converted,'max_tokens':tokens,'stream':stream}
    if adapter=='gemini':
        converted=[]
        for message in messages:
            if message.get('role')=='system':continue
            parts=[{'text':value} if kind=='text' else {'inlineData':{'mimeType':value['mime'],'data':value['data']}}
                   for kind,value in image_parts(message.get('content',''))]
            converted.append({'role':'model' if message['role']=='assistant' else 'user','parts':parts})
        from urllib.parse import quote
        suffix=':streamGenerateContent?alt=sse' if stream else ':generateContent'
        return '/models/'+quote(model,safe='')+suffix,{'contents':converted,'systemInstruction':{'parts':[{'text':system}]},
                  'generationConfig':{'responseMimeType':'application/json','maxOutputTokens':tokens,'temperature':0}}
    token_field='max_completion_tokens' if adapter=='openai' and model.startswith(('gpt-5','o1','o3','o4')) else 'max_tokens'
    payload={'model':model,'messages':messages,'stream':stream,'response_format':{'type':'json_object'},token_field:tokens}
    return '/chat/completions',payload


def answer(data,adapter):
    try:
        if adapter=='ollama':
            if data.get('done_reason')=='length':raise ProviderError('Model nedokončil odpověď. Zkrať zadání nebo zvyš dostupný kontext.')
            text=data['message']['content']
        elif adapter=='anthropic':
            if data.get('stop_reason')=='max_tokens':raise ProviderError('Claude nedokončil odpověď v limitu tokenů.')
            text=''.join(block.get('text','') for block in data['content'] if block.get('type')=='text')
        elif adapter=='gemini':
            candidate=data['candidates'][0]
            if candidate.get('finishReason') not in (None,'STOP'):raise ProviderError('Gemini nedokončil odpověď. Ověř limit a obsah zadání.')
            text=''.join(part.get('text','') for part in candidate['content']['parts'])
        else:
            if data['choices'][0].get('finish_reason')=='length':raise ProviderError('Model nedokončil odpověď v limitu tokenů.')
            text=data['choices'][0]['message']['content']
        result=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip()))
        if not isinstance(result,dict):raise ValueError()
        return result
    except (KeyError,IndexError,TypeError,ValueError,AttributeError) as error:
        if isinstance(error,ProviderError):raise
        raise ProviderError('Model nevrátil platný strukturovaný výsledek. Zkus kompatibilní model.') from None


def verify_local_model(selection):
    profile=selection['profile']
    if profile['id']=='ollama':
        # A tag may have been replaced outside this app since discovery.
        rows=read(profile,selection['key'],'/api/tags').get('models',[])
        if not any(row.get('name')==selection['model'] and type(row.get('size')) is int and row['size']>10_000_000
                   and re.fullmatch('[a-f0-9]{64}',str(row.get('digest',''))) for row in rows if isinstance(row,dict)):
            raise ProviderError('Model není ověřený lokální soubor. Ověř instalované modely.')
        with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
            info=safe_response(client.post(profile['endpoint']+'/api/show',headers=headers(profile,selection['key']),json={'model':selection['model']}))
            if info.get('remote_host') or info.get('remote_model'):raise ProviderError('Lokální režim odmítl cloudový alias modelu.')


def generate(selection,messages,tokens=1800):
    profile=selection['profile'];path,payload=prepare(selection,messages,tokens)
    try:
        verify_local_model(selection)
        # local=True selects the hardened transport, also for cloud: no proxies,
        # redirects, ambient credentials or retries of billable inference.
        response=work.post_json(profile['endpoint']+path,headers=headers(profile,selection['key']),payload=payload,seconds=240,local=True)
        data=safe_response(response)
        result=answer(data,PROVIDERS[profile['id']]['adapter'])
        provided=data.get('usage') or data.get('usageMetadata')
        if isinstance(provided,dict):
            # Usage contains token counts, not provider response bodies or keys.
            fields={'prompt_tokens','completion_tokens','total_tokens','input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens',
                    'promptTokenCount','candidatesTokenCount','totalTokenCount','thoughtsTokenCount'}
            usage={k:v for k,v in provided.items() if k in fields and type(v) is int and v>=0}
            if budget:=work.current():budget.ai_usage=usage
        return result
    except httpx.HTTPError:raise ProviderError('AI server neodpověděl. Požadavek nebyl přeposlán jinému poskytovateli.') from None


def stream(selection,messages,tokens=1800):
    """Text deltas from the provider's own streaming format; caller can close."""
    profile=selection['profile'];adapter=PROVIDERS[profile['id']]['adapter'];path,payload=prepare(selection,messages,tokens,True)
    try:
        verify_local_model(selection)
        with httpx.Client(timeout=60,trust_env=False,follow_redirects=False) as client:
            with client.stream('POST',profile['endpoint']+path,headers=headers(profile,selection['key']),json=payload) as response:
                if response.status_code>=300:raise ProviderError(f'AI stream vrátil HTTP {response.status_code}.')
                for line in response.iter_lines():
                    work.checkpoint()
                    if line.startswith('data:'):line=line[5:].strip()
                    if not line or line.startswith(('event:',':')) or line=='[DONE]':continue
                    try:data=json.loads(line)
                    except ValueError:continue
                    if 'error' in data:raise ProviderError('Poskytovatel ukončil stream chybou.')
                    if adapter=='ollama':delta=data.get('message',{}).get('content','')
                    elif adapter=='anthropic':delta=data.get('delta',{}).get('text','')
                    elif adapter=='gemini':delta=''.join(p.get('text','') for c in data.get('candidates',[]) for p in c.get('content',{}).get('parts',[]))
                    else:delta=''.join(c.get('delta',{}).get('content') or '' for c in data.get('choices',[]))
                    if delta:yield delta
    except httpx.HTTPError:raise ProviderError('Přenos AI streamu byl přerušen.') from None
