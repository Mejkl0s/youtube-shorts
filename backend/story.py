"""Local 3D stories with scene-aligned, explicit male Czech narration."""
import concurrent.futures
import json
import os
import re
import subprocess
import textwrap
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .narration import capabilities, synthesize

router = APIRouter(prefix='/api/story')
ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('RANK_DATA_DIR', str(ROOT / '.runtime'))).resolve() / 'media/stories'
DATA.mkdir(parents=True, exist_ok=True)
pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
lock = threading.Lock()
jobs = {}


class VoicePreview(BaseModel):
    text: str = Field(min_length=1, max_length=160)
    provider: Literal['local', 'piper'] = 'local'


class Story(BaseModel):
    story: Literal['parcel', 'kindness', 'reunion'] = 'parcel'
    duration: Literal[35, 40, 45] = 40
    captions: list[str] = Field(min_length=5, max_length=5)
    voice: bool = True
    provider: Literal['local', 'piper'] = 'local'
    preview: bool = False


def command(args, folder, timeout=180):
    with (folder / 'render.log').open('ab') as log:
        subprocess.run(args, stdout=log, stderr=log, check=True, timeout=timeout)


def update(job_id, **changes):
    with lock:
        jobs[job_id].update(changes)
        folder = DATA / job_id
        temp = folder / 'state.tmp'
        temp.write_text(json.dumps(jobs[job_id], ensure_ascii=False))
        temp.replace(folder / 'state.json')


def narration(body, folder):
    slot = body.duration / 5
    for i, text in enumerate(body.captions):
        source = folder / f'voice_{i}.wav'
        seconds = synthesize(text, body.provider, source)
        speed = max(1, seconds / (slot - .6))
        if speed > 1.2:
            raise ValueError(f'Komentář scény {i+1} je moc dlouhý. Zkrať text nebo vyber delší film; konec slov nebudeme ořezávat.')
        command(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-af', f'aresample=24000,atempo={speed:.6f},adelay=300,apad=whole_len={int(slot*24000)},atrim=end_sample={int(slot*24000)},asetpts=N/SR/TB', '-ar', '24000', '-ac', '1', str(folder / f'segment_{i}.wav')], folder)
    inputs = [item for i in range(5) for item in ['-i', str(folder / f'segment_{i}.wav')]]
    command(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', '[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1[a]', '-map', '[a]', str(folder / 'narration.wav')], folder)


def render(job_id, body):
    folder = DATA / job_id
    try:
        update(job_id, status='running', progress=3, message='Připravuji mužský komentář…' if body.voice and not body.preview else 'Připravuji 3D scénu…')
        if body.voice and not body.preview:
            narration(body, folder)
        config = body.model_dump()
        config['output'] = str(folder)
        (folder / 'config.json').write_text(json.dumps(config))
        update(job_id, progress=10, message='Renderuji skutečnou 3D scénu…')
        command(['blender', '--background', '--threads', '4', '--python', str(ROOT / 'scripts/render_story.py'), '--', str(folder / 'config.json')], folder, 1800)
        if body.preview:
            if not (folder / 'preview.png').is_file():
                raise ValueError('Blender nevytvořil náhled.')
            command(['ffmpeg', '-v', 'error', '-y', '-i', str(folder / 'preview.png'), '-vf', 'hqdn3d=3:3:0:0', '-frames:v', '1', str(folder / 'clean.png')], folder)
            (folder / 'clean.png').replace(folder / 'preview.png')
            update(job_id, status='done', progress=100, message='Skutečný náhled scény je připraven.', image=f'/media/stories/{job_id}/preview.png')
            return
        update(job_id, progress=90, message='Spojuji animaci, titulky a mužský hlas…')
        filters = ['hqdn3d=3:3:0:0']
        for i, text in enumerate(body.captions):
            (folder / f'caption{i}.txt').write_text('\n'.join(textwrap.wrap(text, 24)))
            filters.append(f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile={folder}/caption{i}.txt:expansion=none:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=8:x=(w-tw)/2:y=h-115:enable='gte(t,{i*body.duration/5})*lt(t,{(i+1)*body.duration/5})'")
        audio = ['-i', str(folder / 'narration.wav'), '-c:a', 'aac', '-b:a', '128k'] if body.voice else ['-an']
        command(['ffmpeg', '-v', 'error', '-y', '-framerate', '12', '-i', str(folder / 'frame_%04d.png'), *audio, '-vf', ','.join(filters), '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-t', str(body.duration), '-movflags', '+faststart', str(folder / 'story.mp4')], folder)
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(folder / 'story.mp4')], capture_output=True, check=True, timeout=20)
        info = json.loads(result.stdout)
        if abs(float(info['format']['duration'])-body.duration) > .15:
            raise ValueError('Výsledné video nemá správnou délku.')
        if body.voice and not any(s['codec_type']=='audio' for s in info['streams']):
            raise ValueError('Ve výsledném videu chybí vypravěč.')
        update(job_id, status='done', progress=100, message=f'Hotovo: {body.duration} sekund' + (' s mužským českým hlasem.' if body.voice else ' bez hlasu.'), video=f'/media/stories/{job_id}/story.mp4', duration=body.duration, voice=body.voice, provider=body.provider)
        for frame in folder.glob('frame_*.png'):
            frame.unlink()
    except Exception as error:
        with (folder / 'render.log').open('a') as log:
            log.write('\n' + repr(error) + '\n')
        message = str(error) if isinstance(error, ValueError) else 'Generování se nezdařilo. Zkus nejprve náhled nebo kratší film.'
        update(job_id, status='failed', progress=0, message=message)


@router.get('/capabilities')
def available():
    return capabilities()


@router.post('/voice-preview')
def preview_voice(body: VoicePreview):
    folder = DATA / uuid.uuid4().hex
    folder.mkdir()
    try:
        seconds = synthesize(body.text, body.provider, folder / 'voice.wav')
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return {'audio': f'/media/stories/{folder.name}/voice.wav', 'duration': seconds, 'provider': body.provider}


@router.post('/generate', status_code=202)
def generate(body: Story):
    if any(len(c) > 160 for c in body.captions):
        raise HTTPException(422, 'Komentář scény smí mít nejvýše 160 znaků.')
    if body.voice and not body.preview and any(not c.strip() for c in body.captions):
        raise HTTPException(422, 'Pro vypravěče napiš komentář ke každé scéně.')
    caps = capabilities()
    if not caps['blender']:
        raise HTTPException(503, 'Blender není dostupný.')
    if body.voice and not body.preview and not caps[body.provider]:
        raise HTTPException(409, 'Vybraný hlas není nainstalovaný. Vyber dostupný hlas nebo doinstaluj jeho model.')
    with lock:
        if any(j['status'] in ('queued', 'running') for j in jobs.values()):
            raise HTTPException(409, 'Právě vzniká jiný film. Počkej na dokončení.')
        job_id = uuid.uuid4().hex
        (DATA / job_id).mkdir()
        jobs[job_id] = {'id': job_id, 'status': 'queued', 'progress': 0, 'message': 'Čeká na zpracování…'}
        result = dict(jobs[job_id])
    pool.submit(render, job_id, body)
    return result


@router.get('/jobs/{job_id}')
def status(job_id: str):
    if not re.fullmatch('[a-f0-9]{32}', job_id):
        raise HTTPException(404, 'Úloha nebyla nalezena.')
    with lock:
        result = dict(jobs[job_id]) if job_id in jobs else None
    if result is None:
        saved = DATA / job_id / 'state.json'
        if not saved.is_file():
            raise HTTPException(404, 'Úloha nebyla nalezena.')
        result = json.loads(saved.read_text())
        if result['status'] in ('queued', 'running'):
            return {**result, 'status': 'failed', 'message': 'Server byl během generování restartován. Spusť nový render.'}
    config = DATA / job_id / 'config.json'
    if result['status']=='running' and config.exists():
        cfg = json.loads(config.read_text())
        if not cfg['preview']:
            count = sum(1 for _ in (DATA / job_id).glob('frame_*.png'))
            if count:
                result.update(progress=min(85, 10+int(75*count/(cfg['duration']*12))), message=f'Renderuji 3D snímky: {count}/{cfg["duration"]*12}')
    return result
