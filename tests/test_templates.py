import json
import shutil
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import main as m
from backend import assistant as a
from backend.style import Layout


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    for name in ('media', 'jobs', 'models'):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(m, 'DATA', tmp_path)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('STUDIO_PUBLIC', raising=False)
    monkeypatch.delenv('STUDIO_PASSWORD', raising=False)
    m.jobs.clear()
    return tmp_path


def make_reference(path):
    m.ffmpeg('-f', 'lavfi', '-i', 'color=c=0x181818:s=720x1280', '-vf',
             f"drawtext=fontfile={m.FONT}:text='TOP FIVE MOMENTS':fontsize=46:fontcolor=white:x=(w-tw)/2:y=65,drawtext=fontfile={m.FONT}:text='#5':fontsize=95:fontcolor=0xCAFA63:x=50:y=250,drawtext=fontfile={m.FONT}:text='THE PERFECT MOMENT':fontsize=37:fontcolor=white:x=(w-tw)/2:y=1020",
             '-frames:v', '1', str(path))


def test_free_template_match_uses_real_ocr_and_never_paid_api(isolated, monkeypatch):
    make_reference(isolated / 'template.png')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder-not-used')
    monkeypatch.setattr(m, 'ai_request', lambda *args, **kw: pytest.fail('Free template called paid AI'))
    client = TestClient(m.app)
    uploaded = client.post('/api/templates/upload', files={'file': ('template.png', (isolated / 'template.png').read_bytes(), 'image/png')}).json()
    response = client.post(f'/api/templates/{uploaded["id"]}/analyze', json={'mode': 'free', 'instructions': 'Preserve the lime number.'})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['analysis_mode'] == 'free' and result['analyzed']
    assert set(result['detected']) == {'číslo', 'nadpis', 'titulky'}
    layout = Layout.model_validate(result['layout'])
    assert abs(layout.rank_y - 250/1280) < .04 and abs(layout.rank_x - 50/720) < .04
    assert abs(layout.title_y - 65/1280) < .025 and abs(layout.caption_y - 1020/1280) < .04
    color = [int(layout.rank_color[index:index+2], 16) for index in (0, 2, 4)]
    assert max(abs(np.array(color) - np.array([202, 250, 99]))) < 25
    assert result['instructions'] == 'Preserve the lime number.'


def test_no_recognized_text_retains_user_layout_and_reports_limit(isolated):
    image = isolated / 'blank.png'
    m.ffmpeg('-f', 'lavfi', '-i', 'color=c=black:s=180x320', '-frames:v', '1', str(image))
    client = TestClient(m.app)
    ref = client.post('/api/templates/upload', files={'file': ('blank.png', image.read_bytes(), 'image/png')}).json()
    expected = Layout(rank_color='FF00AA', rank_y=.42)
    response = client.post(f'/api/templates/{ref["id"]}/analyze', json={'base_layout': expected.model_dump()})
    assert response.status_code == 200
    result = response.json()
    assert result['analyzed'] is False and not result['detected']
    assert result['layout'] == expected.model_dump()
    assert 'nepodařilo' in result['notes']


def test_video_template_selects_actual_frame_and_rejects_outside_duration(isolated):
    video = isolated / 'reference.mp4'
    m.ffmpeg('-f', 'lavfi', '-i', 'color=c=black:s=360x640:r=15:d=3', '-f', 'lavfi', '-i', 'color=c=black:s=360x640:r=15:d=3', '-filter_complex',
             f"[0:v]drawtext=fontfile={m.FONT}:text='#5':fontsize=75:fontcolor=yellow:x=20:y=100[v0];[1:v]drawtext=fontfile={m.FONT}:text='#1':fontsize=75:fontcolor=red:x=160:y=200[v1];[v0][v1]concat=n=2:v=1:a=0[v]",
             '-map', '[v]', '-c:v', 'libx264', str(video))
    client = TestClient(m.app)
    ref = client.post('/api/templates/upload', files={'file': ('example.mp4', video.read_bytes(), 'video/mp4')}).json()
    assert ref['kind'] == 'video' and ref['duration'] == 6
    result = client.post(f'/api/templates/{ref["id"]}/analyze', json={'frame_time': 4, 'mode': 'free'}).json()
    assert result['frame_time'] == 4 and result['url'] != ref['url']
    assert result['layout']['rank_x'] > .35 and result['layout']['rank_y'] > .25
    color = result['layout']['rank_color']
    assert int(color[:2], 16) > 180 and int(color[2:4], 16) < 60
    assert client.post(f'/api/templates/{ref["id"]}/analyze', json={'frame_time': 6}).status_code == 400


def test_saved_manual_style_and_instructions_reach_assistant(isolated, monkeypatch):
    make_reference(isolated / 'reference.png')
    client = TestClient(m.app)
    ref = client.post('/api/templates/upload', files={'file': ('ref.png', (isolated / 'reference.png').read_bytes(), 'image/png')}).json()
    settings = Layout(rank_color='FF00AA', title_align='left', title_x=.12, caption_align='right', caption_x=.1)
    result = client.post(f'/api/templates/{ref["id"]}/settings', json={'layout': settings.model_dump(), 'instructions': 'Keep the pink ranking marker.'})
    assert result.status_code == 200 and result.json()['analysis_mode'] == 'manual'
    assert a.reference(ref['id'])['layout'] == settings.model_dump()
    payloads = []
    def planned(payload):
        payloads.append(payload)
        return {'reply': 'Použiji uložený vzhled.', 'actions': []}
    monkeypatch.setattr(m, 'ai_request', planned)
    a.plan_request(a.Request(message='Použij předlohu.', reference_id=ref['id'], state=a.State(layout=settings)))
    data = json.dumps(payloads[0])
    assert 'Keep the pink ranking marker.' in data and 'FF00AA' in data
    assert client.post(f'/api/templates/{ref["id"]}/settings', json={'layout': {'rank_color': 'white;movie=/etc/passwd'}}).status_code == 422


def test_template_position_color_and_alignment_are_used_in_actual_mp4(isolated):
    source = isolated / 'blank.mp4'
    m.ffmpeg('-f', 'lavfi', '-i', 'color=c=black:s=180x320:r=15:d=3', '-c:v', 'libx264', str(source))
    clips = []
    for _ in range(5):
        asset_id = uuid.uuid4().hex
        folder = isolated / 'media' / asset_id
        folder.mkdir()
        shutil.copyfile(source, folder / 'source')
        m.register(folder / 'source', asset_id, 'Moment')
        clips.append(m.Clip(id=asset_id, title='Moment', voiceover='Timing makes this moment stand out.', duration=2))
    layout = Layout(rank_color='FF00AA', rank_x=.62, rank_y=.34, title_align='left', title_x=.12,
                    caption_align='right', caption_x=.1, show_label=False, show_criteria=False)
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'status': 'queued'}
    m.render(job_id, m.Project(title='TOP FIVE', clips=clips, layout=layout, voice=False, effects=False, resolution='720'))
    assert m.jobs[job_id]['status'] == 'done', m.jobs[job_id]
    raw = m.ffmpeg('-ss', '1', '-i', str(isolated / 'jobs' / job_id / 'ranking.mp4'), '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1')
    image = np.frombuffer(raw, dtype=np.uint8).reshape(1280, 720, 3)
    pink = (image[:,:,0] > 170) & (image[:,:,1] < 70) & (image[:,:,2] > 90)
    ys, xs = np.where(pink)
    assert abs(xs.min() - .62*720) < 18 and abs(ys.min() - .34*1280) < 10
    white = np.all(image > 190, axis=2)
    top_y, top_x = np.where(white[:250])
    assert abs(top_x.min() - .12*720) < 15
    bottom_y, bottom_x = np.where(white[900:])
    assert abs(bottom_x.max() - .9*720) < 15


def test_updated_reference_preferences_reach_planner_and_vision_action(isolated, monkeypatch):
    make_reference(isolated / 'reference.png')
    client = TestClient(m.app)
    ref = client.post('/api/templates/upload', files={'file': ('ref.png', (isolated / 'reference.png').read_bytes(), 'image/png')}).json()
    payloads = []
    def provider(payload):
        payloads.append(payload)
        if len(payloads) == 1:
            return {'reply': 'Přizpůsobím předlohu.', 'actions': ['analyze_template']}
        return {'layout': Layout(rank_color='FF00AA').model_dump(), 'notes': 'Růžové číslo.'}
    monkeypatch.setattr(m, 'ai_request', provider)
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'status': 'queued'}
    a.run_assistant(job_id, a.Request(message='Použij předlohu s těmito změnami.', reference_id=ref['id'], reference_instructions='Keep the number pink and large.'))
    assert m.jobs[job_id]['status'] == 'done', m.jobs[job_id]
    assert len(payloads) == 2
    for payload in payloads:
        assert 'Keep the number pink and large.' in json.dumps(payload)
    assert a.reference(ref['id'])['instructions'] == 'Keep the number pink and large.'
    assert m.jobs[job_id]['project']['layout']['rank_color'] == 'FF00AA'
