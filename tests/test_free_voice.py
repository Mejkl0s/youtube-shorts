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


@pytest.mark.parametrize(('rank_style', 'effects'), [('outline', False), ('badge', True), ('plain', True)])
def test_keyless_voice_is_actually_mixed_into_five_clip_mp4_export(isolated, monkeypatch, rank_style, effects):
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
        clips.append({'id': identity, 'title': 'Timing', 'voiceover': '', 'narration_mode': 'rank', 'duration': 2})
    client = TestClient(m.app)
    result = client.post('/api/render', json={'title': 'FREE VOICE TOP FIVE', 'clips': clips, 'voice': True, 'effects': effects, 'resolution': '720', 'layout': {'rank_display': 'single', 'rank_style': rank_style, 'rank_size': .18, 'rank_color': 'FFD84D'}, 'voice_settings': {'provider': 'edge', 'voice': 'free_male', 'speed': .95}})
    assert result.status_code == 202, result.text
    deadline = time.monotonic()+60
    while time.monotonic() < deadline:
        job = client.get('/api/jobs/'+result.json()['id']).json()
        if job['status'] in ('done', 'failed'):
            break
        time.sleep(.1)
    assert job['status'] == 'done', job
    assert len(calls) == 5
    assert [call['text'] for call in calls] == m.rank_lines('en')
    output = folder/'jobs'/result.json()['id']/'ranking.mp4'
    raw = m.ffmpeg('-i', str(output), '-vn', '-ac', '1', '-f', 's16le', 'pipe:1')
    assert np.abs(np.frombuffer(raw, dtype='<i2').astype(float)).mean() > 50
    samples = np.frombuffer(raw, dtype='<i2').astype(float)
    for index in range(5):
        # TTS fixture starts at 0.4 s. The beginning isolates the effect from
        # narration; the later interval verifies the real mixed TTS fixture.
        beginning = samples[int((index*2+.02)*44100):int((index*2+.17)*44100)]
        speech = samples[int((index*2+.7)*44100):int((index*2+.85)*44100)]
        assert np.abs(speech).mean() > 300
        assert (np.abs(beginning).mean() > 100) == effects
    # Inspect the actual encoded rank region, not a mocked FFmpeg command.
    pixels = m.ffmpeg('-ss', '1', '-i', str(output), '-frames:v', '1', '-vf',
                      'crop=250:150:20:215,format=rgb24', '-f', 'rawvideo', 'pipe:1')
    rgb = np.frombuffer(pixels, dtype=np.uint8).reshape(-1, 3)
    assert ((rgb[:, 0] > 200) & (rgb[:, 1] > 150) & (rgb[:, 2] < 130)).sum() > 300
    black = (rgb.max(axis=1) < 35).sum()
    assert black > 300 if rank_style != 'plain' else black < 100
    assert client.get(job['download']).headers['content-type'] == 'video/mp4'
    preview = client.get(job['download'].replace('/download', '/preview'))
    assert preview.status_code == 200 and preview.content == output.read_bytes()
    assert preview.headers['content-disposition'].startswith('inline;')
    ranged = client.get(job['download'].replace('/download', '/preview'), headers={'Range': 'bytes=0-255'})
    assert ranged.status_code == 206 and ranged.content == output.read_bytes()[:256]


@pytest.mark.parametrize('language', ['en', 'cs'])
def test_free_rank_announcements_are_short_explicit_and_never_call_paid_ai(isolated, monkeypatch, language):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder-never-used')
    monkeypatch.setattr(m, 'ai_request', lambda *a, **kw: pytest.fail('Rank announcement called AI'))
    clips = [{'id': uuid.uuid4().hex, 'title': 'Winter fails', 'voiceover': ''} for _ in range(5)]
    response = TestClient(m.app).post('/api/scripts', json={'clips': clips, 'language': language, 'mode': 'rank', 'max_words': 4})
    assert response.status_code == 200, response.text
    assert response.json() == {'mode': 'rank', 'lines': m.rank_lines(language)}
    assert all(m.word_count(line) == 2 for line in response.json()['lines'])
    for clip in clips:
        clip.update(voiceover='Number one.', narration_mode='rank')
    project = m.Project(title='Winter fails', clips=list(reversed(clips)), language=language)
    assert [clip.voiceover for clip in project.clips] == m.rank_lines(language)
