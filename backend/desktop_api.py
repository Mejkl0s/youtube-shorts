"""Desktop-only APIs; native filesystem access additionally needs a main-only token."""
import hmac
import os
from pathlib import Path
import re
import shutil
import threading
import uuid

from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,Field

from . import desktop_store as store
from . import desktop_models as models
from .desktop_secrets import atomic_json

router=APIRouter(prefix='/api/desktop')
shutdown_callback=None


def admin(request):
    secret=os.environ.get('RANK_DESKTOP_ADMIN_TOKEN','')
    if not secret or not hmac.compare_digest(request.headers.get('x-rank-desktop-admin','').encode(),secret.encode()):raise HTTPException(403,'Tato operace vyžaduje nativní dialog aplikace.')


@router.get('/state')
def get_state():return {'state':store.state_get()}


@router.post('/state')
def put_state(body:store.StateBody):store.state_put(body.state);return {'saved':True}


@router.get('/projects')
def projects():return {'projects':store.project_list()}


@router.post('/projects')
def save_project(body:store.StateBody):return {'id':store.save_project(body.state)}


@router.get('/projects/{identity}')
def get_project(identity:str):return {'state':store.project_get(identity)}


@router.get('/hardware')
def get_hardware():return models.hardware()


@router.get('/models')
def get_models():return models.service_status()


class DownloadBody(BaseModel):model:str=Field(max_length=200)
class DeleteBody(DownloadBody):confirmation:str=Field(max_length=200)


@router.post('/models/download',status_code=202)
def download(body:DownloadBody):return models.download(body.model)


@router.post('/models/download/{identity}/cancel')
def cancel(identity:str):return models.cancel_download(identity)


@router.post('/models/delete')
def delete(body:DeleteBody):return models.delete(body.model,body.confirmation)


@router.post('/service/start')
def start_service():return models.start_service()


@router.post('/service/stop')
def stop_service():
    from . import main as m
    if any(j.get('status') not in ('done','failed') for j in m.jobs.values()):raise HTTPException(409,'Před zastavením služby dokonči nebo zastav úlohy.')
    return models.stop_service()


class DirectoryBody(BaseModel):directory:str=Field(max_length=4000)


@router.post('/models/storage')
def model_storage(body:DirectoryBody,request:Request):admin(request);return models.set_storage(body.directory)


@router.post('/migrate')
def migrate(body:DirectoryBody,request:Request):
    admin(request)
    source=Path(body.directory).resolve();destination=store.root()
    # Accept a studio project directory or its runtime only; no generic file read.
    if (source/'.runtime').is_dir():source=source/'.runtime'
    if source==destination or not (source/'media').is_dir():raise HTTPException(400,'Vyber původní složku studia s .runtime/media.')
    records=[];total=0
    for category in ('media','templates','models'):
        folder=source/category
        if not folder.exists():continue
        if folder.is_symlink() or not folder.resolve().is_relative_to(source.resolve()):raise HTTPException(400,'Migrace nepodporuje odkazy mimo původní data.')
        for path in folder.rglob('*'):
            if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):raise HTTPException(400,'Migrace nepodporuje odkazy mimo původní data.')
            if not path.is_file():continue
            relative=path.relative_to(source)
            # Never copy .env, credentials, sessions or executable files.
            if any(p.startswith('.') for p in relative.parts):continue
            if path.name!='source' and path.suffix.lower() not in ('.mp4','.jpg','.jpeg','.png','.json','.wav','.onnx','.webp'):continue
            target=destination/relative
            if not target.resolve().is_relative_to(destination.resolve()) or any(p.is_symlink() for p in (target,*target.parents)):
                raise HTTPException(400,'Cílová cesta obsahuje odkaz mimo data aplikace.')
            if target.exists():
                import hashlib
                with path.open('rb') as a,target.open('rb') as b:
                    if hashlib.file_digest(a,'sha256').digest()!=hashlib.file_digest(b,'sha256').digest():raise HTTPException(409,'V cíli existuje odlišný soubor se stejným názvem. Nic nebylo přepsáno.')
                continue
            records.append((path,target));total+=path.stat().st_size
    if shutil.disk_usage(destination).free<total+50*1024**2:raise HTTPException(409,'Pro kopii původních dat není dost místa.')
    created=[]
    try:
        for original,target in records:
            target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name('.migration-'+uuid.uuid4().hex)
            try:shutil.copy2(original,temporary);temporary.replace(target);created.append(target)
            finally:temporary.unlink(missing_ok=True)
        atomic_json(destination/'private'/'desktop'/'migration.json',{'source':str(source),'files':len(created)})
    except Exception:
        for target in created:target.unlink(missing_ok=True)
        raise HTTPException(500,'Kopírování selhalo; nové soubory byly vráceny. Původní data se nemění.') from None
    return {'files':len(created),'message':'Média a lokální hlasy zkopírovány. Projekt a historii z prohlížeče přenes přes Export projektu; přístupové klíče a cookies se nekopírují.'}


@router.post('/cancel-all')
def cancel_all():
    from . import work_budget as work
    work.cancel_all()
    for identity in list(models._downloads):models.cancel_download(identity)
    return {'cancel_requested':True}


@router.get('/activity')
def activity():
    from . import main as m
    jobs=[{k:row.get(k) for k in ('id','kind','status','message','progress')} for row in list(m.jobs.values()) if row.get('status') not in ('done','failed')]
    jobs.extend({**row['state'],'kind':'model-download'} for row in list(models._downloads.values()) if row['state']['status']=='downloading')
    return {'jobs':jobs}


@router.post('/shutdown')
def shutdown(request:Request):
    admin(request);cancel_all();models.shutdown()
    if shutdown_callback:threading.Timer(.2,shutdown_callback).start()
    return {'stopping':True}
