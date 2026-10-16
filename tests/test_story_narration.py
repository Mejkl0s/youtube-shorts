import json
import wave
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app
from backend import narration as speech
from backend import story


@pytest.mark.parametrize('duration', [35, 40, 45])
def test_supported_story_duration(duration):
    assert story.Story(duration=duration, captions=['A short line.']*5).duration == duration


@pytest.mark.parametrize('change', [{'duration': 36}, {'provider': 'unknown'}, {'captions': ['one']}, {'story': '../outside'}])
def test_invalid_story_configuration(change):
    with pytest.raises(ValidationError):
        story.Story(**{'captions': ['Text']*5, **change})


def test_missing_neural_voice_does_not_silently_fall_back(tmp_path, monkeypatch):
    monkeypatch.setattr(speech, 'MODELS', tmp_path)
    with pytest.raises(ValueError, match='Ryan is not installed'):
        speech.synthesize('Hello there.', 'piper', tmp_path/'missing.wav')
    assert not (tmp_path/'missing.wav').exists()


def test_voice_does_not_cut_off_long_sentences(tmp_path, monkeypatch):
    monkeypatch.setattr(story, 'synthesize', lambda *args: 20)
    with pytest.raises(ValueError, match='Shorten the line'):
        story.narration(story.Story(duration=35, captions=['A long line.']*5), tmp_path)
    assert not (tmp_path/'segment_0.wav').exists()


def test_rejects_empty_narration_and_concurrent_renders(monkeypatch):
    client = TestClient(app)
    assert client.post('/api/story/generate', json={'captions': ['']*5}).status_code == 422
    monkeypatch.setattr(story, 'jobs', {'active': {'status': 'running'}})
    monkeypatch.setattr(story, 'capabilities', lambda: {'blender': True, 'local': True, 'piper': False})
    assert client.post('/api/story/generate', json={'captions': ['Text']*5}).status_code == 409
    assert client.get('/api/story/jobs/../outside').status_code == 404


def test_finished_job_is_readable_after_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(story, 'DATA', tmp_path)
    job_id = 'a'*32
    folder = tmp_path/job_id
    folder.mkdir()
    payload = {'id': job_id, 'status': 'done', 'video': '/media/stories/'+job_id+'/story.mp4'}
    (folder/'state.json').write_text(json.dumps(payload))
    assert story.status(job_id) == payload
    (folder/'state.json').write_text(json.dumps({**payload, 'status': 'running'}))
    assert story.status(job_id)['status'] == 'failed'


def test_real_english_male_voice_and_action_alignment(tmp_path):
    if not speech.capabilities()['local']:
        pytest.skip('Install espeak-ng or run scripts/install_speech.sh for actual speech integration.')
    text = 'He picked up the parcel. Its owner was nearby.'
    story.narration(story.Story(duration=35, captions=[text]*5), tmp_path)
    with wave.open(str(tmp_path/'narration.wav'), 'rb') as audio:
        assert audio.getnchannels() == 1
        assert audio.getnframes()/audio.getframerate() == 35
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16)
        for scene in np.array_split(samples, 5):
            assert np.max(np.abs(scene.astype(np.int32))) > 1000


def test_actual_speech_leaves_breaths_and_covers_key_actions(tmp_path):
    if not speech.capabilities()['local']:
        pytest.skip('Local speech integration requires eSpeak NG.')
    body=story.Story(duration=35,captions=['He noticed the parcel. Someone had left it behind.']*5)
    events=story.narration(body,tmp_path)
    with wave.open(str(tmp_path/'narration.wav'),'rb') as audio:
        rate=audio.getframerate()
        samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype=np.int16)
    assert len(samples)==35*rate
    for index,event in enumerate(events):
        start=round(event['speech_start']*rate)
        assert np.abs(samples[start:start+rate].astype(np.int32)).max()>1000
        next_start=events[index+1]['speech_start'] if index<4 else 35
        gap=samples[round(event['speech_end']*rate):round(next_start*rate)]
        assert len(gap)>=int(.4*rate)
        assert np.count_nonzero(gap)==0
    assert events[2]['speech_start']==15.75
    assert events[3]['speech_start']==22.75
    assert sum(e['speech_end']-e['speech_start'] for e in events)<35*.84
