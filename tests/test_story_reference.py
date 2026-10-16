import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app, ffmpeg
from backend import story
from backend.story_reference import ReferenceRequest, StyleProfile, prepare_reference, reference, ai_style
from backend.storyboard import ACTIONS, beat_plan


@pytest.mark.parametrize('url', ['http://youtube.com/watch?v=abcdefghijk', 'https://127.0.0.1/secret.mp4', 'https://example.com/a.mp4', 'https://www.youtube.com@127.0.0.1/watch?v=abcdefghijk', 'https://www.youtube.com:444/watch?v=abcdefghijk', 'https://www.instagram.com/account/'])
def test_reference_rejects_unsupported_or_private_network_urls(url):
    with pytest.raises(ValidationError):
        ReferenceRequest(url=url)


@pytest.mark.parametrize('url', ['https://www.youtube.com/shorts/abcdefghijk', 'https://youtu.be/abcdefghijk', 'https://www.tiktok.com/@creator/video/123456', 'https://www.instagram.com/reel/abc123/'])
def test_supported_public_reference_urls(url):
    assert ReferenceRequest(url=url).url == url


def test_ai_requires_configured_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    response = TestClient(app).post('/api/story/references', json={'url': 'https://youtu.be/abcdefghijk', 'mode': 'ai'})
    assert response.status_code == 409
    assert 'Basic visual analysis' in response.json()['detail']


def test_actual_reference_frames_and_style_persist(tmp_path, monkeypatch):
    fixture = tmp_path/'fixture.mp4'
    ffmpeg('-f', 'lavfi', '-i', 'color=c=red:size=160x240:rate=12:duration=2', '-f', 'lavfi', '-i', 'color=c=blue:size=160x240:rate=12:duration=2', '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-c:v', 'libx264', str(fixture))
    job_id = 'b'*32
    data = tmp_path/'media';folder=data/job_id;folder.mkdir(parents=True)
    monkeypatch.setattr(story, 'DATA', data)
    monkeypatch.setattr(story, 'jobs', {job_id: {'id': job_id, 'status': 'queued'}})
    def downloaded(args, output, timeout):
        assert 'yt_dlp' in args and '--ignore-config' in args and '--no-playlist' in args
        assert args[-1]=='https://youtu.be/abcdefghijk'
        shutil.copyfile(fixture, output/'reference.mp4')
    monkeypatch.setattr(story, 'command', downloaded)
    prepare_reference(job_id, ReferenceRequest(url='https://youtu.be/abcdefghijk'))
    assert story.jobs[job_id]['status']=='done'
    result=reference(job_id)
    assert result['mode']=='basic'
    assert len(result['frames'])==3
    assert all((folder/f'reference-frame-{i}.jpg').stat().st_size>0 for i in range(3))
    assert result['style']['coat_primary'] != result['style']['coat_secondary']
    assert result['style']['lighting']=='moody'
    assert 'does not understand the story' in result['notes']


def test_download_failure_never_announces_analyzed_reference(tmp_path, monkeypatch):
    job_id='c'*32;folder=tmp_path/job_id;folder.mkdir()
    monkeypatch.setattr(story, 'DATA', tmp_path)
    monkeypatch.setattr(story, 'jobs', {job_id:{'id':job_id,'status':'queued'}})
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1,['yt_dlp'])
    monkeypatch.setattr(story,'command',fail)
    prepare_reference(job_id,ReferenceRequest(url='https://youtu.be/abcdefghijk'))
    assert story.jobs[job_id]['status']=='failed'
    assert not (folder/'reference.json').exists()


def test_ai_receives_actual_images_and_bounded_style(tmp_path, monkeypatch):
    from backend import main
    frames=[]
    for i in range(3):
        path=tmp_path/f'{i}.jpg';path.write_bytes(b'actual-test-frame');frames.append(path)
    def analyze(payload):
        images=[item for item in payload['messages'][1]['content'] if item['type']=='image_url']
        assert len(images)==3
        assert all(item['image_url']['url'].startswith('data:image/jpeg;base64,') for item in images)
        return {'style':{'coat_primary':'FF4433','framing':'close'},'notes':'Approximate colors and framing only.'}
    monkeypatch.setattr(main,'ai_request',analyze)
    style,notes=ai_style(frames)
    assert style.coat_primary=='FF4433' and style.framing=='close'
    assert 'Approximate' in notes
    with pytest.raises(ValidationError):StyleProfile(coat_primary='invalid;code',framing='arbitrary')


@pytest.mark.parametrize('duration',[35,40,45])
def test_key_actions_share_the_narration_timeline(duration):
    beats=beat_plan(duration)
    assert beats[2]['speech_start']==ACTIONS['pickup']*duration
    assert beats[3]['speech_start']==ACTIONS['handoff']*duration
    assert beats[4]['speech_start']>=ACTIONS['depart']*duration
    assert all(cue['start']<=cue['speech_start']<cue['end'] for cue in beats)
    assert beats[-1]['end']==duration
