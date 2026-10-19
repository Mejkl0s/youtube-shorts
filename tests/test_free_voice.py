import shutil
import time
import uuid

import edge_tts
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import main as m
from backend.free_voice import MALE_VOICES


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    for directory in ('media', 'jobs', 'models'):
        (tmp_path/directory).mkdir()
    monkeypatch.setattr(m, 'DATA', tmp_path)
    media = next(route.app for route in m.app.routes if getattr(route, 'name', None) == 'media')
    monkeypatch.setattr(media, 'directory', tmp_path/'media')
    monkeypatch.setattr(media, 'all_directories', [tmp_path/'media'])
    for key in ('OPENAI_API_KEY', 'ELEVENLABS_API_KEY', 'STUDIO_PASSWORD', 'STUDIO_PUBLIC'):
        monkeypatch.delenv(key, raising=False)
    m.jobs.clear()
    # The remote voice is simulated, while encoding, decoding, muxing and API execution are real.
    fixture = tmp_path/'provider.mp3'
    m.ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.55', '-c:a', 'libmp3lame', str(fixture))
    calls = []
    class Speech:
        def __init__(self, text, **options):
            options['proxy_configured'] = bool(options.pop('proxy', None))
            calls.append({'text': text, **options})
        async def save(self, path):
            shutil.copyfile(fixture, path)
    monkeypatch.setattr(edge_tts, 'Communicate', Speech)
    monkeypatch.setattr(m.httpx, 'post', lambda *args, **kw: pytest.fail('Free speech called a paid provider'))
    return tmp_path, calls


@pytest.mark.parametrize('language,text', [('en', 'That timing wins this round.'), ('cs', 'Tohle načasování rozhodlo o vítězství.')])
def test_keyless_preview_selects_male_voice_and_returns_real_decoded_audio(isolated, language, text):
    folder, calls = isolated
    client = TestClient(m.app)
    health = client.get('/api/health').json()
    assert health['free_voice'] and not health['ai_scripts'] and not health['elevenlabs']
    result = client.post('/api/voice-preview', json={'text': text, 'language': language, 'voice_settings': {'provider': 'edge', 'voice': 'free_male', 'speed': .95}})
    assert result.status_code == 200, result.text
    assert len(calls) == 1 and calls[0]['voice'] == MALE_VOICES[language]
    assert calls[0]['rate'] == '-5%' and calls[0]['text'] == text
    audio = client.get(result.json()['url'])
    assert audio.status_code == 200 and audio.content[:4] == b'RIFF'
    assert len(audio.content) > 10000
    assert not list((folder/'media').glob('free-voice-*'))


def test_free_provider_failure_is_clear_private_and_never_triggers_paid_fallback(isolated, monkeypatch):
    folder, calls = isolated
    class FailedSpeech:
        def __init__(self, *args, **options):
            pass
        async def save(self, path):
            with open(path, 'wb') as output:
                output.write(b'partial-provider-response')
            raise RuntimeError('Proxy URL contains secret-test-token')
    monkeypatch.setattr(edge_tts, 'Communicate', FailedSpeech)
    client = TestClient(m.app)
    result = client.post('/api/voice-preview', json={'text': 'That timing wins this round.', 'voice_settings': {'provider': 'edge', 'voice': 'free_male'}})
    assert result.status_code == 409
    assert 'Bezplatný online hlas teď není dostupný' in result.text
    assert 'secret-test-token' not in result.text and 'OPENAI_API_KEY' not in result.text
    assert list((folder/'media').iterdir()) == []
    assert client.post('/api/voice-preview', json={'text': 'Test.', 'voice_settings': {'provider': 'edge', 'voice': 'echo'}}).status_code == 422


def test_keyless_voice_is_actually_mixed_into_five_clip_mp4_export(isolated, monkeypatch):
    folder, calls = isolated
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder-never-used')
    source = folder/'source.mp4'
    m.ffmpeg('-f', 'lavfi', '-i', 'color=c=blue:s=160x284:r=15:d=3', '-c:v', 'libx264', str(source))
    clips = []
    for index in range(5):
        identity = uuid.uuid4().hex
        directory = folder/'media'/identity
        directory.mkdir()
        shutil.copyfile(source, directory/'source')
        m.register(directory/'source', identity, 'Timing')
        clips.append({'id': identity, 'title': 'Timing', 'voiceover': 'That timing wins this round.', 'duration': 2})
    client = TestClient(m.app)
    result = client.post('/api/render', json={'title': 'FREE VOICE TOP FIVE', 'clips': clips, 'voice': True, 'effects': False, 'resolution': '720', 'voice_settings': {'provider': 'edge', 'voice': 'free_male', 'speed': .95}})
    assert result.status_code == 202, result.text
    deadline = time.monotonic()+60
    while time.monotonic() < deadline:
        job = client.get('/api/jobs/'+result.json()['id']).json()
        if job['status'] in ('done', 'failed'):
            break
        time.sleep(.1)
    assert job['status'] == 'done', job
    assert len(calls) == 5
    output = folder/'jobs'/result.json()['id']/'ranking.mp4'
    raw = m.ffmpeg('-i', str(output), '-vn', '-ac', '1', '-f', 's16le', 'pipe:1')
    assert np.abs(np.frombuffer(raw, dtype='<i2').astype(float)).mean() > 50
    assert client.get(job['download']).headers['content-type'] == 'video/mp4'
