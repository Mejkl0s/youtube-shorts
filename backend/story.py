"""Local 3D stories with scene-aligned, English narration aligned with action cues."""
import concurrent.futures
import json
import os
import re
import subprocess
import textwrap
import threading
import uuid
import wave
import numpy as np
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .narration import capabilities, synthesize
from .storyboard import beat_plan

router = APIRouter(prefix='/api/story')
ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('RANK_DATA_DIR', str(ROOT / '.runtime'))).resolve() / 'media/stories'
DATA.mkdir(parents=True, exist_ok=True)
pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
lock = threading.Lock()
jobs = {}


class VoicePreview(BaseModel):
    text: str = Field(min_length=1, max_length=160)
    provider: Literal['local', 'piper', 'openai'] = 'local'


class Story(BaseModel):
    story: Literal['parcel', 'kindness', 'reunion'] = 'parcel'
    duration: Literal[35, 40, 45] = 40
    captions: list[str] = Field(min_length=5, max_length=5)
    voice: bool = True
    provider: Literal['local', 'piper', 'openai'] = 'local'
    preview: bool = False
    reference_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')


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
    rate = 24000
    plan = beat_plan(body.duration, body.story)
    output = np.zeros(body.duration * rate, dtype=np.int16)
    events = []
    spoken_samples = 0
    for i, (text, cue) in enumerate(zip(body.captions, plan)):
        chunks = []
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
        for j, sentence in enumerate(sentences):
            source = folder / f'voice_{i}_{j}.wav'
            seconds = synthesize(sentence, body.provider, source)
            if seconds > (cue['end'] - cue['speech_start'] - .45) * 1.1:
                raise ValueError(f'Scene {i+1} is too wordy. Shorten the line or choose a longer film.')
            normalized = folder / f'pcm_{i}_{j}.wav'
            command(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-af', 'aresample=24000,asetpts=N/SR/TB', '-ar', str(rate), '-ac', '1', '-c:a', 'pcm_s16le', str(normalized)], folder)
            with wave.open(str(normalized), 'rb') as audio:
                if j:
                    chunks.append(np.zeros(int(.26 * rate), dtype=np.int16))
                chunks.append(np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16))
        if not chunks:
            raise ValueError(f'Scene {i+1} needs a narration line.')
        samples = np.concatenate(chunks)
        available = cue['end'] - cue['speech_start'] - .45
        speed = max(1, len(samples) / rate / available)
        if speed > 1.1:
            raise ValueError(f'Scene {i+1} is too wordy for its action window. Shorten the line or choose a longer film; words will not be cut off.')
        if speed > 1:
            joined = folder / f'joined_{i}.wav'
            with wave.open(str(joined), 'wb') as audio:
                audio.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
                audio.writeframes(samples.tobytes())
            fitted = folder / f'fitted_{i}.wav'
            command(['ffmpeg', '-v', 'error', '-y', '-i', str(joined), '-af', f'atempo={speed:.6f}', '-c:a', 'pcm_s16le', str(fitted)], folder)
            with wave.open(str(fitted), 'rb') as audio:
                samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16)
        start = round(cue['speech_start'] * rate)
        end = start + len(samples)
        if end > round((cue['end'] - .4) * rate):
            raise ValueError(f'Scene {i+1} does not leave a natural pause. Shorten its narration.')
        output[start:end] = samples
        spoken_samples += len(samples)
        events.append({**cue, 'speech_end': end/rate, 'text': text, 'speed': speed})
    if spoken_samples / len(output) > .84:
        raise ValueError('The narration leaves too little breathing room. Shorten a few lines to keep natural pauses.')
    with wave.open(str(folder / 'narration.wav'), 'wb') as audio:
        audio.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        audio.writeframes(output.tobytes())
    (folder / 'narration-timing.json').write_text(json.dumps(events, indent=2))
    return events


def render(job_id, body):
    folder = DATA / job_id
    try:
        update(job_id, status='running', progress=3, message='Preparing English narration…' if body.voice and not body.preview else 'Preparing the 3D scene…')
        if body.voice and not body.preview:
            narration(body, folder)
        config = body.model_dump()
        config['output'] = str(folder)
        if body.reference_id:
            from .story_reference import reference
            config['style'] = reference(body.reference_id)['style']
        (folder / 'config.json').write_text(json.dumps(config))
        update(job_id, progress=10, message='Rendering the actual 3D scene…')
        command(['blender', '--background', '--threads', '4', '--python', str(ROOT / 'scripts/render_story.py'), '--', str(folder / 'config.json')], folder, 1800)
        if body.preview:
            if not (folder / 'preview.png').is_file():
                raise ValueError('Blender did not create a preview.')
            command(['ffmpeg', '-v', 'error', '-y', '-i', str(folder / 'preview.png'), '-vf', 'hqdn3d=3:3:0:0', '-frames:v', '1', str(folder / 'clean.png')], folder)
            (folder / 'clean.png').replace(folder / 'preview.png')
            update(job_id, status='done', progress=100, message='The actual scene preview is ready.', image=f'/media/stories/{job_id}/preview.png')
            return
        update(job_id, progress=90, message='Combining animation, captions and narration…')
        filters = ['hqdn3d=3:3:0:0']
        for i, (text, cue) in enumerate(zip(body.captions, beat_plan(body.duration, body.story))):
            (folder / f'caption{i}.txt').write_text('\n'.join(textwrap.wrap(text, 24)))
            filters.append(f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile={folder}/caption{i}.txt:expansion=none:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=8:x=(w-tw)/2:y=h-115:enable='gte(t,{cue['start']})*lt(t,{cue['end']})'")
        audio = ['-i', str(folder / 'narration.wav'), '-c:a', 'aac', '-b:a', '128k'] if body.voice else ['-an']
        command(['ffmpeg', '-v', 'error', '-y', '-framerate', '12', '-i', str(folder / 'frame_%04d.png'), *audio, '-vf', ','.join(filters), '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-t', str(body.duration), '-movflags', '+faststart', str(folder / 'story.mp4')], folder)
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(folder / 'story.mp4')], capture_output=True, check=True, timeout=20)
        info = json.loads(result.stdout)
        if abs(float(info['format']['duration'])-body.duration) > .15:
            raise ValueError('The video duration is incorrect.')
        if body.voice and not any(s['codec_type']=='audio' for s in info['streams']):
            raise ValueError('The exported video is missing its narration.')
        update(job_id, status='done', progress=100, message=f'Done: {body.duration} seconds' + (' with an English male narrator.' if body.voice else ' without narration.'), video=f'/media/stories/{job_id}/story.mp4', duration=body.duration, voice=body.voice, provider=body.provider)
        for frame in folder.glob('frame_*.png'):
            frame.unlink()
    except Exception as error:
        with (folder / 'render.log').open('a') as log:
            log.write('\n' + repr(error) + '\n')
        message = str(error) if isinstance(error, ValueError) else 'Generation failed. Try a scene preview or a shorter film.'
        update(job_id, status='failed', progress=0, message=message)


@router.get('/capabilities')
def available():
    return {**capabilities(), 'beats': beat_plan(1)}


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
        raise HTTPException(422, 'Each scene narration must be at most 160 characters.')
    if body.voice and not body.preview and any(not c.strip() for c in body.captions):
        raise HTTPException(422, 'Write a narration line for each scene.')
    if body.reference_id:
        from .story_reference import reference
        reference(body.reference_id)
    caps = capabilities()
    if not caps['blender']:
        raise HTTPException(503, 'Blender is unavailable.')
    if body.voice and not body.preview and not caps[body.provider]:
        raise HTTPException(409, 'The selected voice is unavailable. Choose an installed voice or configure its provider.')
    with lock:
        if any(j['status'] in ('queued', 'running') for j in jobs.values()):
            raise HTTPException(409, 'Another job is running. Wait for it to finish.')
        job_id = uuid.uuid4().hex
        (DATA / job_id).mkdir()
        jobs[job_id] = {'id': job_id, 'status': 'queued', 'progress': 0, 'message': 'Queued…'}
        result = dict(jobs[job_id])
    pool.submit(render, job_id, body)
    return result


@router.get('/jobs/{job_id}')
def status(job_id: str):
    if not re.fullmatch('[a-f0-9]{32}', job_id):
        raise HTTPException(404, 'Job not found.')
    with lock:
        result = dict(jobs[job_id]) if job_id in jobs else None
    if result is None:
        saved = DATA / job_id / 'state.json'
        if not saved.is_file():
            raise HTTPException(404, 'Job not found.')
        result = json.loads(saved.read_text())
        if result['status'] in ('queued', 'running'):
            return {**result, 'status': 'failed', 'message': 'The server restarted during generation. Start a new render.'}
    config = DATA / job_id / 'config.json'
    if result['status']=='running' and config.exists():
        cfg = json.loads(config.read_text())
        if not cfg['preview']:
            count = sum(1 for _ in (DATA / job_id).glob('frame_*.png'))
            if count:
                result.update(progress=min(85, 10+int(75*count/(cfg['duration']*12))), message=f'Rendering 3D frames: {count}/{cfg["duration"]*12}')
    return result
