import json
import time
import uuid
import io
import wave
import shutil
import os
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main as m
from backend import assistant as a
from backend.style import Layout, VoiceSettings


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    # Exercise actual filter paths with Windows-like punctuation and Czech names.
    name = "O'Brien [Windows], ž; studio"
    tmp_path = tmp_path/(('Drive C: ' if os.name != 'nt' else '')+name)
    tmp_path.mkdir()
    portable_fonts = {}
    for name, original in m.FONTS.items():
        target = tmp_path/Path(original).name
        shutil.copyfile(original, target)
        portable_fonts[name] = str(target)
    monkeypatch.setattr(m, 'FONTS', portable_fonts)
    for directory in ['media', 'jobs', 'models']:
        (tmp_path / directory).mkdir()
    monkeypatch.setattr(m, 'DATA', tmp_path)
    monkeypatch.setattr(m, 'MODELS', tmp_path / 'models')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)
    with m.job_lock:
        m.jobs.clear()
    yield tmp_path


def make_source(folder, color='red', duration=3):
    folder.mkdir(exist_ok=True)
    m.ffmpeg('-f', 'lavfi', '-i', f'color=c={color}:s=160x284:r=15:d={duration}', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-f', 'mp4', str(folder / 'source'))
    asset_id = folder.name
    return m.register(folder / 'source', asset_id, f'{color} test clip')


def test_real_export_five_segments_with_original_effects(isolated):
    colors = ['red', 'green', 'blue', 'yellow', 'purple']
    clips = []
    for color in colors:
        asset_id = uuid.uuid4().hex
        make_source(isolated / 'media' / asset_id, color)
        clips.append({'id': asset_id, 'title': f'{color} moment', 'voiceover': 'The timing makes this moment stand out.', 'duration': 2, 'start': 0.5})
    client = TestClient(m.app)
    response = client.post('/api/render', json={'title': "TOP 5: YOU'RE #1 [100%]", 'ranking_criteria': 'Timing and surprise', 'clips': clips, 'voice': False, 'effects': True, 'captions': True, 'resolution': '720'})
    assert response.status_code == 202, response.text
    job_id = response.json()['id']
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        job = client.get(f'/api/jobs/{job_id}').json()
        if job['status'] in ['done', 'failed']:
            break
        time.sleep(0.2)
    assert job['status'] == 'done', job
    output = isolated / 'jobs' / job_id / 'ranking.mp4'
    metadata = m.probe(output)
    video = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in metadata['streams'] if s['codec_type'] == 'audio')
    assert (video['width'], video['height']) == (720, 1280)
    assert video['codec_name'] == 'h264' and audio['codec_name'] == 'aac'
    assert abs(float(metadata['format']['duration']) - 10) < 0.2
    # Verify ordering from real decoded pixels, away from text overlays.
    expected = [(255, 0, 0), (0, 128, 0), (0, 0, 255), (255, 255, 0), (128, 0, 128)]
    for index, color in enumerate(expected):
        pixels = m.ffmpeg('-ss', str(index * 2 + 1), '-i', str(output), '-frames:v', '1', '-vf', 'crop=2:2:10:900,format=rgb24', '-f', 'rawvideo', 'pipe:1')
        sample = np.frombuffer(pixels, dtype=np.uint8).reshape(-1, 3).mean(axis=0)
        assert max(abs(sample - color)) < 18, (index, sample, color)
    raw_audio = m.ffmpeg('-i', str(output), '-vn', '-ac', '1', '-f', 's16le', 'pipe:1')
    assert np.abs(np.frombuffer(raw_audio, dtype='<i2').astype(float)).mean() > 100
    download = client.get(f'/api/jobs/{job_id}/download')
    assert download.status_code == 200 and download.headers['content-type'] == 'video/mp4'
    assert download.content == output.read_bytes()


def test_scene_windows_do_not_cross_compilation_cut(isolated):
    source = isolated / 'compilation.mp4'
    m.ffmpeg('-f', 'lavfi', '-i', 'color=c=red:s=160x284:r=24:d=3', '-f', 'lavfi', '-i', 'color=c=blue:s=160x284:r=24:d=5', '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-c:v', 'libx264', str(source))
    windows = m.scene_windows(source)
    assert len(windows) == 2
    assert any(abs(start - 3) < 0.1 for start, _ in windows)
    for start, duration in windows:
        assert not start < 3 < start + duration - 0.01
        assert 2 <= duration <= 5


def test_word_limit_and_exactly_five_clips():
    assert m.word_count("That recovery turns failure into a win.") == 7
    assert m.word_count("That's a well-timed move.") == 4
    assert m.word_count('Skvělý střih, číslo 1!') == 4
    with pytest.raises(ValidationError):
        m.Clip(id='a' * 32, title='clip', voiceover='This sentence has far too many separate words.')
    with pytest.raises(ValidationError):
        m.Project(title='TOP 5', clips=[], voice=False)
    same = m.Clip(id='a' * 32, title='clip', voiceover='Great timing wins this round.')
    with pytest.raises(ValidationError):
        m.Project(title='TOP 5', clips=[same] * 5)


@pytest.mark.parametrize('url,allowed', [
    ('https://www.tiktok.com/@creator/video/123456789', True),
    ('https://www.instagram.com/reel/ABC_123-/', True),
    ('https://www.youtube.com/shorts/IujvEGCadfU', True),
    ('https://youtu.be/IujvEGCadfU', True),
    ('https://www.youtube.com/watch?v=IujvEGCadfU', True),
    ('https://www.tiktok.com/@creator', False),
    ('https://www.instagram.com/creator/', False),
    ('https://tiktok.com.evil.test/@creator/video/123', False),
    ('https://www.tiktok.com:444/@creator/video/123', False),
    ('https://evil@www.instagram.com/reel/ABC/', False),
    ('http://127.0.0.1/video', False),
    ('file:///etc/passwd', False),
])
def test_provider_video_url_restrictions(url, allowed):
    assert m.social_url(url, True) == allowed
    if 'youtu' in url:
        assert not m.social_url(url, False)


def test_missing_integrations_and_invalid_upload_fail_honestly(isolated):
    client = TestClient(m.app)
    assert client.get('/api/health').json()['voices']['en'] is False
    assert client.post('/api/discover', json={'topic': 'funny cats', 'mode': 'ai'}).status_code == 409
    assert client.post('/api/voice-preview', json={'text': 'Great timing wins this round.'}).status_code == 409
    assert client.post('/api/research', json={'topic': 'ranking Shorts'}).status_code == 409
    response = client.post('/api/upload', files={'file': ('bad.mp4', b'not a video', 'video/mp4')})
    assert response.status_code == 400
    assert list((isolated / 'media').iterdir()) == []


def test_visual_ai_selection_preserves_source_length_and_rejects_duplicate(isolated, monkeypatch):
    candidates = []
    for _ in range(5):
        asset_id = uuid.uuid4().hex
        candidate = make_source(isolated / 'media' / asset_id, duration=9)
        candidate['source_url'] = 'https://www.instagram.com/reel/ABC/'
        candidates.append(candidate)
    # Real frame extraction and scene analysis; only the remote response is mocked.
    selection = {'clips': [{'scene': i * 4, 'title': f'Moment {i}', 'voiceover': 'Great timing wins this round.', 'reason': 'A clearly visible moment with good timing.'} for i in range(5)]}
    monkeypatch.setattr(m, 'ai_request', lambda *a, **kw: selection)
    result = m.select_candidates(candidates, 'timing', 'en')
    assert len({c['id'] for c in result}) == 5
    assert all(c['sourceDuration'] == 9 for c in result)
    assert all(c['duration'] == 5 for c in result)
    selection['clips'][1]['scene'] = 0
    with pytest.raises(ValueError, match='stejné video'):
        m.select_candidates(candidates, 'timing', 'en')


def test_research_discards_uncited_channel_links(isolated, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder')
    monkeypatch.setattr(m, 'ai_request', lambda *a, **kw: {'channels': [
        {'name': 'Supported example', 'url': 'https://www.youtube.com/shorts/IujvEGCadfU', 'observation': 'A ranking title.', 'evidence': 'Search metadata'},
        {'name': 'Invented channel', 'url': 'https://www.youtube.com/@invented', 'observation': 'Not supported'},
    ], '_evidence_urls': ['https://www.youtube.com/shorts/IujvEGCadfU'], 'recommendations': [], 'limitations': 'Metadata only'})
    result = m.research(m.ResearchRequest())
    assert [c['name'] for c in result['channels']] == ['Supported example']


def test_reference_image_upload_is_real_and_paid_analysis_requires_key(isolated):
    image = isolated / 'reference.png'
    m.ffmpeg('-f', 'lavfi', '-i', 'color=c=yellow:s=180x320', '-frames:v', '1', str(image))
    client = TestClient(m.app)
    result = client.post('/api/templates/upload', files={'file': ('my-template.png', image.read_bytes(), 'image/png')})
    assert result.status_code == 200, result.text
    reference = result.json()
    assert reference['analyzed'] is False
    assert (isolated / 'media' / reference['id'] / 'frame.jpg').stat().st_size > 100
    assert client.post(f'/api/templates/{reference["id"]}/analyze', json={'mode': 'ai'}).status_code == 409
    bad = client.post('/api/templates/upload', files={'file': ('fake.png', b'not an image', 'image/png')})
    assert bad.status_code == 400


def test_template_settings_reject_injected_filters_and_out_of_range_values():
    with pytest.raises(ValidationError):
        Layout(rank_color='white;movie=/etc/passwd')
    with pytest.raises(ValidationError):
        Layout(font='/etc/passwd')
    with pytest.raises(ValidationError):
        Layout(caption_y=2)
    assert Layout(rank_color='#ff00aa').rank_color == 'FF00AA'


def test_voice_provider_is_explicit_and_never_silently_falls_back(isolated):
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        m.synthesize('Great timing wins this round.', 'en', isolated / 'speech.wav')
    with pytest.raises(ValidationError):
        VoiceSettings(provider='openai', voice='adam')
    with pytest.raises(ValidationError):
        VoiceSettings(provider='elevenlabs')


def test_selected_male_voice_receives_delivery_and_valid_audio(isolated, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder')
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(np.zeros(24000, dtype='<i2').tobytes())
    calls = []
    class Response:
        status_code = 200
        content = buffer.getvalue()
    def remote(url, **kwargs):
        calls.append((url, kwargs['json']))
        return Response()
    monkeypatch.setattr(m.httpx, 'post', remote)
    output = isolated / 'speech.wav'
    m.synthesize('Great timing wins this round.', 'en', output, VoiceSettings(voice='echo', speed=0.95, delivery='Natural male delivery with measured emphasis.'))
    assert calls[0][0] == 'https://api.openai.com/v1/audio/speech'
    payload = calls[0][1]
    assert payload['voice'] == 'echo' and payload['speed'] == 0.95
    assert 'measured emphasis' in payload['instructions']
    assert m.probe(output)['streams'][0]['codec_type'] == 'audio'


def test_assistant_edits_reorders_and_really_exports(isolated, monkeypatch):
    clips = []
    for color in ['red', 'green', 'blue', 'yellow', 'purple']:
        asset_id = uuid.uuid4().hex
        make_source(isolated / 'media' / asset_id, color)
        clips.append({'id': asset_id, 'title': color, 'voiceover': 'Great timing wins this round.', 'start': 0.5, 'duration': 2})
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder')
    # Only natural-language interpretation is mocked; actions and export are real.
    monkeypatch.setattr(m, 'ai_request', lambda *args, **kwargs: {'reply': 'Otočím pořadí, změním šablonu a exportuji.', 'changes': {'voice': False, 'layout': {'rank_color': 'FF00AA'}, 'title': 'TOP FIVE REVERSED'}, 'order': [4, 3, 2, 1, 0], 'actions': ['render']})
    client = TestClient(m.app)
    response = client.post('/api/assistant', json={'message': 'Otoč pořadí a exportuj bez hlasu.', 'state': {'clips': clips, 'resolution': '720'}})
    assert response.status_code == 202, response.text
    job_id = response.json()['id']
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = client.get(f'/api/jobs/{job_id}').json()
        if result['status'] in ('done', 'failed'):
            break
        time.sleep(0.2)
    assert result['status'] == 'done', result
    assert result['project']['layout']['rank_color'] == 'FF00AA'
    assert result['project']['clips'][0]['title'] == 'purple'
    assert result['project']['clips'][0]['sourceDuration'] == 3
    assert client.get(result['download']).headers['content-type'] == 'video/mp4'
    assert client.get(f'/api/jobs/{job_id}/download').status_code == 409


def test_assistant_cannot_execute_arbitrary_tools_or_unsafe_plan(isolated, monkeypatch):
    client = TestClient(m.app)
    assert client.post('/api/assistant', json={'message': 'Najdi pět klipů.'}).status_code == 409
    with pytest.raises(ValidationError):
        a.Plan(reply='ok', actions=['shell'])
    with pytest.raises(ValidationError):
        a.Plan(reply='ok', actions=['discover', 'discover'])
    with pytest.raises(ValidationError):
        a.Plan(reply='ok', order=[0, 0, 1, 2, 3])
    monkeypatch.setattr(m, 'ai_request', lambda *args, **kwargs: {'reply': 'Jaké téma?', 'question': 'Jaké téma?', 'actions': ['discover']})
    with pytest.raises(ValueError, match='nejednoznačný'):
        a.plan_request(a.Request(message='Najdi pět klipů.'))


def test_assistant_shortens_long_narration_instead_of_rushing_voice(isolated, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder')
    clips = []
    for _ in range(5):
        asset_id = uuid.uuid4().hex
        make_source(isolated / 'media' / asset_id)
        clips.append(m.Clip(id=asset_id, title='Timing', voiceover='Great timing wins this round.', duration=2))
    # Simulated provider durations, actual FFmpeg audio/video processing.
    def speech(text, language, path, config=None):
        seconds = 3 if m.word_count(text) > 2 else 0.6
        with wave.open(str(path), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(np.zeros(int(24000*seconds), dtype='<i2').tobytes())
    monkeypatch.setattr(m, 'synthesize', speech)
    monkeypatch.setattr(m, 'ai_request', lambda *args, **kwargs: {'line': 'Perfect timing.'})
    project = m.Project(title='TIMING RANKING', clips=clips, auto_shorten=True, resolution='720')
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'status': 'queued', 'progress': 0}
    m.render(job_id, project)
    assert m.jobs[job_id]['status'] == 'done', m.jobs[job_id]
    assert all(c.voiceover == 'Perfect timing.' for c in project.clips)
    assert (isolated / 'jobs' / job_id / 'caption-5.txt').read_text() == 'Perfect timing.'
