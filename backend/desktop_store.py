"""Versioned project/state storage and portable, bounded project archives."""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path,PurePosixPath
import re
import shutil
import sqlite3
import stat
import tempfile
import threading
import time
import uuid
import zipfile

from fastapi import APIRouter,HTTPException,UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,field_validator

exchange_router=APIRouter(prefix='/api/project-exchange')
KEYS={'rank-studio-project','rank-studio-chat','rank-studio-assets','rank-studio-sources','rank-studio-previous-clips','rank-studio-writing'}
MAX_ARCHIVE=8*1024**3
MAX_ENTRY=1024**3
_lock=threading.RLock()


def root():
    from . import main as m
    return m.DATA


class StateBody(BaseModel):
    state:dict[str,str]=Field(default_factory=dict,max_length=6)

    @field_validator('state')
    @classmethod
    def valid(cls,value):
        if not set(value)<=KEYS or sum(len(v.encode()) for v in value.values())>8*1024**2:
            raise ValueError('Projekt je příliš velký nebo obsahuje nepovolené položky.')
        for key,text in value.items():
            parsed=json.loads(text)
            if key=='rank-studio-project':
                if not isinstance(parsed,dict) or not isinstance(parsed.get('clips'),list) or len(parsed['clips'])!=5:
                    raise ValueError('Projekt musí mít pět pozic pro klipy.')
            elif key=='rank-studio-writing':
                if not isinstance(parsed,dict) or not isinstance(parsed.get('prompt',''),str):raise ValueError('Rozepsané zadání není platné.')
            elif not isinstance(parsed,list):raise ValueError('Historie musí být seznam.')
        return value


@contextmanager
def database():
    folder=root()/'private'/'desktop';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'projects.sqlite3'
    db=sqlite3.connect(path,timeout=15)
    version=db.execute('PRAGMA user_version').fetchone()[0]
    if version>1:
        db.close();raise ValueError('Databáze je z novější verze aplikace. Nebyla změněna.')
    if version==0:
        if path.stat().st_size:
            backup=sqlite3.connect(folder/f'projects-before-v1-{time.time_ns()}.sqlite3')
            try:db.backup(backup)
            finally:backup.close()
        db.executescript('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY,value TEXT NOT NULL);'
                         'CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY,title TEXT NOT NULL,state TEXT NOT NULL,updated REAL NOT NULL);'
                         'PRAGMA user_version=1;')
    db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback();raise
    finally:db.close()


def state_get():
    with _lock, database() as db:return dict(db.execute('SELECT key,value FROM state'))


def state_put(state):
    StateBody(state=state)
    with _lock,database() as db:
        db.execute('DELETE FROM state')
        db.executemany('INSERT INTO state(key,value) VALUES (?,?)',state.items())


def save_project(state):
    StateBody(state=state)
    project=json.loads(state.get('rank-studio-project','{}'))
    title=str(project.get('title') or 'Nový projekt')[:100]
    identity=uuid.uuid4().hex
    with _lock,database() as db:
        db.execute('INSERT INTO projects VALUES (?,?,?,?)',(identity,title,json.dumps(state),time.time()))
    return identity


def project_list():
    with _lock,database() as db:
        return [{'id':i,'title':title,'updated':updated} for i,title,updated in db.execute('SELECT id,title,updated FROM projects ORDER BY updated DESC LIMIT 200')]


def project_get(identity):
    if not re.fullmatch('[a-f0-9]{32}',identity):raise HTTPException(404,'Projekt nebyl nalezen.')
    with _lock,database() as db:row=db.execute('SELECT state FROM projects WHERE id=?',(identity,)).fetchone()
    if not row:raise HTTPException(404,'Projekt nebyl nalezen.')
    return json.loads(row[0])


def identities(value):
    if isinstance(value,dict):return set().union(*(identities(item) for item in value.values())) if value else set()
    if isinstance(value,list):return set().union(*(identities(item) for item in value)) if value else set()
    if isinstance(value,str):
        return {value} if re.fullmatch('[a-f0-9]{32}',value) else set(re.findall(r'/(?:media|templates)/([a-f0-9]{32})(?:/|$)',value))
    return set()


def referenced_files(state):
    # History IDs are retained as history, not as a request to package every
    # video ever downloaded. Include the active project, undo clips and parents.
    related=[state[key] for key in ('rank-studio-project','rank-studio-previous-clips') if key in state]
    wanted=set().union(*(identities(json.loads(value)) for value in related)) if related else set()
    seen=set();result={}
    while wanted-seen:
        identity=next(iter(wanted-seen));seen.add(identity)
        for category in ('media','templates'):
            folder=root()/category/identity
            if folder.is_symlink() or not folder.resolve().is_relative_to(root().resolve()):raise ValueError('Export nepodporuje odkazy mimo data aplikace.')
            if not folder.is_dir():continue
            metadata=folder/'metadata.json'
            if metadata.is_file():wanted.update(identities(json.loads(metadata.read_text(encoding='utf-8'))))
            for path in folder.iterdir():
                if path.is_symlink():raise ValueError('Export nepodporuje odkazy mimo data aplikace.')
                if path.is_file() and (path.name=='source' or path.suffix.lower() in ('.json','.mp4','.jpg','.jpeg','.png','.wav','.webp')):
                    result[path.relative_to(root()).as_posix()]=path
    return result


def make_bundle(state):
    StateBody(state=state)
    files=referenced_files(state)
    total=sum(p.stat().st_size for p in files.values())
    if total>MAX_ARCHIVE or len(files)>3000:raise ValueError('Projekt překračuje limit přenosného archivu 8 GB.')
    if shutil.disk_usage(root()).free<total+50*1024**2:raise ValueError('Pro export projektu není dost místa na disku.')
    folder=root()/'private'/'project-exports';folder.mkdir(parents=True,exist_ok=True)
    identity=uuid.uuid4().hex;target=folder/(identity+'.rankstudio')
    digests={}
    for name,path in files.items():
        with path.open('rb') as source:digests[name]=hashlib.file_digest(source,'sha256').hexdigest()
    manifest={'version':1,'state':state,'files':digests}
    try:
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
            archive.writestr('project.json',json.dumps(manifest,ensure_ascii=False))
            for name,path in files.items():archive.write(path,name)
        return identity
    except Exception:
        target.unlink(missing_ok=True);raise


def safe_member(member):
    path=PurePosixPath(member.filename)
    reserved={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
    if (path.is_absolute() or member.orig_filename!=member.filename or member.filename!=path.as_posix() or '\\' in member.orig_filename or any(part in ('.','..') for part in path.parts)
            or path.name.split('.')[0].upper() in reserved
            or stat.S_ISLNK(member.external_attr>>16) or member.flag_bits&1 or member.is_dir()):return False
    if member.filename=='project.json':return member.file_size<=9*1024**2
    return (len(path.parts)==3 and path.parts[0] in ('media','templates')
            and re.fullmatch('[a-f0-9]{32}',path.parts[1]) and re.fullmatch('[A-Za-z0-9_.-]{1,120}',path.parts[2])
            and (path.name=='source' or path.suffix.lower() in ('.json','.mp4','.jpg','.jpeg','.png','.wav','.webp'))
            and member.file_size<=MAX_ENTRY)


def import_bundle(path):
    (root()/'private').mkdir(parents=True,exist_ok=True)
    with _lock,zipfile.ZipFile(path) as archive:
        members=archive.infolist();names=[row.filename for row in members]
        if (len(members)>3001 or len({name.casefold() for name in names})!=len(names)
                or 'project.json' not in names or any(not safe_member(row) for row in members)
                or sum(row.file_size for row in members)>MAX_ARCHIVE):
            raise ValueError('Archiv obsahuje nepovolené cesty, odkazy nebo příliš mnoho dat.')
        manifest=json.loads(archive.read('project.json'))
        if manifest.get('version')!=1 or not isinstance(manifest.get('files'),dict):raise ValueError('Nepodporovaná verze projektu.')
        state=StateBody(state=manifest['state']).state
        if set(manifest['files'])!=set(names)-{'project.json'}:raise ValueError('Seznam souborů projektu nesouhlasí.')
        size=sum(row.file_size for row in members)
        if shutil.disk_usage(root()).free<size+50*1024**2:raise ValueError('Pro import není dost místa na disku.')
        with tempfile.TemporaryDirectory(prefix='project-import-',dir=root()/'private') as temp:
            staged=[];created=[]
            for name,digest in manifest['files'].items():
                if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Neplatný kontrolní součet projektu.')
                target=Path(temp)/name;target.parent.mkdir(parents=True,exist_ok=True)
                checksum=hashlib.sha256()
                with archive.open(name) as source,target.open('wb') as output:
                    while chunk:=source.read(1024**2):checksum.update(chunk);output.write(chunk)
                if checksum.hexdigest()!=digest:raise ValueError('Kontrolní součet souboru nesouhlasí.')
                final=root()/name
                if not final.resolve().is_relative_to(root().resolve()) or any(parent.is_symlink() for parent in [final,*final.parents] if parent!=root().parent):
                    raise ValueError('Import nepodporuje odkazy v datovém adresáři.')
                if final.exists():
                    with final.open('rb') as existing:old=hashlib.file_digest(existing,'sha256').hexdigest()
                    if old!=digest:raise ValueError('Projekt používá stejné ID pro odlišné video. Původní data nebyla přepsána.')
                else:staged.append((target,final))
            try:
                for source,target in staged:
                    target.parent.mkdir(parents=True,exist_ok=True);source.replace(target);created.append(target)
                identity=save_project(state)
            except Exception:
                for target in created:target.unlink(missing_ok=True)
                raise
    return {'id':identity,'state':state,'files':len(manifest['files'])}


@exchange_router.post('/export')
def export_project(body:StateBody):
    try:identity=make_bundle(body.state)
    except (ValueError,OSError) as error:raise HTTPException(400,str(error)) from None
    return {'id':identity,'url':'/api/project-exchange/download/'+identity}


@exchange_router.get('/download/{identity}')
def download_project(identity:str):
    if not re.fullmatch('[a-f0-9]{32}',identity):raise HTTPException(404,'Archiv nebyl nalezen.')
    path=root()/'private'/'project-exports'/(identity+'.rankstudio')
    if not path.is_file():raise HTTPException(404,'Archiv nebyl nalezen.')
    return FileResponse(path,filename='Rank-Studio-projekt.rankstudio',media_type='application/zip')


@exchange_router.post('/import')
async def upload_project(file:UploadFile):
    folder=root()/'private';folder.mkdir(parents=True,exist_ok=True)
    path=folder/('incoming-'+uuid.uuid4().hex+'.zip')
    try:
        total=0
        with path.open('wb') as output:
            while chunk:=await file.read(1024**2):
                total+=len(chunk)
                if total>MAX_ARCHIVE:raise ValueError('Archiv překračuje limit 8 GB.')
                output.write(chunk)
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(import_bundle,path)
    except (ValueError,OSError,KeyError,zipfile.BadZipFile):raise HTTPException(400,'Projekt nelze importovat: neplatný archiv, kolize nebo nedostatek místa. Původní projekt zůstal zachovaný.') from None
    finally:path.unlink(missing_ok=True);await file.close()
