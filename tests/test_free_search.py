import shutil
import time
import uuid
from urllib.parse import quote
from xml.sax.saxutils import escape

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import main as m
from backend import free_search as f


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    for directory in ('media', 'jobs', 'models'):
        (tmp_path / directory).mkdir()
    monkeypatch.setattr(m, 'DATA', tmp_path)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('STUDIO_PASSWORD', raising=False)
    monkeypatch.delenv('STUDIO_PUBLIC', raising=False)
    monkeypatch.setattr(m, 'youtube_search', lambda *args: ([], []))
    with m.job_lock:
        m.jobs.clear()
    return tmp_path


def results(count=6):
    return [{'url': f'https://www.tiktok.com/@catclips/video/{100000 + index}', 'title': f'Funny cats moment {index}', 'description': 'Funny cats jumping'} for index in range(count)]


def test_actual_rss_and_html_parsing_preserves_sources():
    url = 'https://www.tiktok.com/@catclips/video/12345'
    rss = '<rss><channel><item><title>Funny &amp; fast cats</title><link>' + escape(url) + '</link><description>&lt;b&gt;Cats&lt;/b&gt; jump</description></item></channel></rss>'
    assert f.rss_results(rss) == [{'url': url, 'title': 'Funny & fast cats', 'description': 'Cats jump'}]
    parser = f.DuckResults()
    parser.feed('<a class="result__a" href="//duckduckgo.com/l/?uddg=' + quote(url, safe='') + '"><b>Funny</b> cats</a><a href="https://example.org">Unrelated</a>')
    assert parser.results == [{'url': url, 'title': 'Funny cats', 'description': ''}]


@pytest.mark.parametrize('document', ['<html>Challenge</html>', '<!DOCTYPE rss [<!ENTITY x "cats">]><rss/>'])
def test_invalid_engine_documents_fail_without_bypass(document):
    with pytest.raises(ValueError):
        f.rss_results(document)


def test_search_filters_unrelated_profiles_foreign_hosts_and_duplicates(monkeypatch):
    samples = results(1) + [
        {'url': results(1)[0]['url'] + '?tracking=1', 'title': 'Funny cats', 'description': ''},
        {'url': 'https://www.tiktok.com/@catclips', 'title': 'Funny cats', 'description': ''},
        {'url': 'https://www.tiktok.com.evil.example/@a/video/1', 'title': 'Funny cats', 'description': ''},
        {'url': 'https://www.tiktok.com/@a/video/12346', 'title': 'Football skill', 'description': ''},
        {'url': 'https://www.youtube.com/shorts/IujvEGCadfU', 'title': 'Funny cats', 'description': ''},
        {'url': 'https://www.instagram.com/reel/cats123/', 'title': 'Funny cats jump', 'description': ''},
    ]
    monkeypatch.setattr(f, 'engine_results', lambda *args: samples)
    entries, _ = f.public_search('funny cats', False, 8)
    assert {entry['url'] for entry in entries} == {results(1)[0]['url'], 'https://www.instagram.com/reel/cats123/'}


def test_search_fallback_and_youtube_option(monkeypatch):
    def search(query, engine):
        if engine == 'bing':
            raise ValueError('limited')
        return [{'url': 'https://www.youtube.com/shorts/IujvEGCadfU', 'title': 'Funny cats', 'description': ''}]
    monkeypatch.setattr(f, 'engine_results', search)
    entries, warnings = f.public_search('funny cats', True, 8)
    assert len(entries) == 1 and entries[0]['provider'] == 'duckduckgo'
    assert warnings


def test_http_challenge_is_not_followed_or_treated_as_results(monkeypatch):
    original = httpx.Client
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, text='Challenge')
    monkeypatch.setattr(f.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(ValueError, match='429'):
        f.engine_results('funny cats', 'bing')
    assert len(calls) == 1 and calls[0].url.host == 'www.bing.com'


def test_free_endpoint_needs_no_key_and_paid_mode_still_requires_one(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(m.executor, 'submit', lambda *args: calls.append(args))
    client = TestClient(m.app)
    response = client.post('/api/discover', json={'topic': 'funny cats'})
    assert response.status_code == 202
    assert calls[0][2].mode == 'free'
    assert client.get('/api/health').json()['free_search'] is True
    assert client.post('/api/discover', json={'topic': 'funny cats', 'mode': 'ai'}).status_code == 409
    assert client.post('/api/discover', json={'topic': '   '}).status_code == 422


def test_missing_downloads_preserve_real_found_links_without_success(isolated, monkeypatch):
    entries = results()
    monkeypatch.setattr(m, 'public_search', lambda *args: (entries, []))
    monkeypatch.setattr(m, 'download_candidate', lambda *args: (_ for _ in ()).throw(ValueError('Unavailable')))
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'status': 'queued'}
    m.discover(job_id, m.DiscoverRequest(topic='funny cats'))
    job = m.jobs[job_id]
    assert job['status'] == 'failed' and '0 videí' in job['message']
    assert [entry['url'] for entry in job['search_results']] == [entry['url'] for entry in entries]
    assert not job.get('clips')


def test_free_search_to_real_scene_selection_and_export_never_calls_paid_api(isolated, monkeypatch):
    # Real source: a three-second black intro followed by a moving test scene.
    source = isolated / 'fixture.mp4'
    m.ffmpeg('-f', 'lavfi', '-i', 'color=c=black:s=160x284:r=24:d=3', '-f', 'lavfi', '-i', 'testsrc2=s=160x284:r=24:d=3',
             '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-c:v', 'libx264', str(source))
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder-never-used')
    monkeypatch.setattr(m, 'ai_request', lambda *args, **kw: pytest.fail('Free flow called a paid AI API'))
    monkeypatch.setattr(f, 'engine_results', lambda *args: results())
    original = m.run
    downloads = []
    def download(args, timeout=180):
        if 'yt_dlp' in args:
            downloads.append(args[-1])
            output = args[args.index('-o') + 1].replace('%(ext)s', 'mp4')
            shutil.copyfile(source, output)
            return b''
        return original(args, timeout)
    monkeypatch.setattr(m, 'run', download)
    client = TestClient(m.app)
    response = client.post('/api/discover', json={'topic': 'funny cats', 'mode': 'free', 'allow_youtube': False, 'candidate_count': 8})
    assert response.status_code == 202
    job_id = response.json()['id']
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        job = client.get('/api/jobs/' + job_id).json()
        if job['status'] in ('done', 'failed'):
            break
        time.sleep(.1)
    assert job['status'] == 'done', job
    assert len(job['clips']) == len({clip['id'] for clip in job['clips']}) == 5
    assert len(downloads) == 6
    assert all(clip['start'] >= 2.9 and clip['start'] + clip['duration'] <= 6.05 for clip in job['clips'])
    assert all(clip['voiceover'] == '' and clip['source_url'] in downloads for clip in job['clips'])
    render_id = uuid.uuid4().hex
    m.jobs[render_id] = {'id': render_id, 'status': 'queued'}
    project = m.Project(title='TOP 5 CATS', clips=job['clips'], voice=False, resolution='720')
    m.render(render_id, project)
    assert m.jobs[render_id]['status'] == 'done', m.jobs[render_id]
    output = m.DATA / 'jobs' / render_id / 'ranking.mp4'
    video = next(stream for stream in m.probe(output)['streams'] if stream['codec_type'] == 'video')
    assert (video['width'], video['height']) == (720, 1280)
    assert client.get('/api/jobs/' + render_id + '/download').status_code == 200


def youtube_results(count=5):
    return [{'url': f'https://www.youtube.com/shorts/CATCLIP{i:04d}', 'title': f'Funny cats moment {i}', 'source': 'YouTube'} for i in range(count)]


@pytest.mark.parametrize('initial_count', [0, 8])
def test_youtube_gets_own_budget_after_social_download_failures(isolated, monkeypatch, initial_count):
    monkeypatch.setattr(m, 'public_search', lambda *args: (results(initial_count), []))
    searches, downloaded = [], []
    monkeypatch.setattr(m, 'youtube_search', lambda *args: (searches.append(args) or youtube_results(), []))
    monkeypatch.setattr(m, 'ai_request', lambda *args, **kw: pytest.fail('Free fallback called paid AI'))
    def download(item):
        downloaded.append(item['url'])
        if item['source'] == 'TikTok':
            raise ValueError('Sign in required; opaque-session-secret')
        return {'id': uuid.uuid4().hex, 'name': item['title'], 'source': item['source'], 'source_url': item['url'], 'duration': 4}
    monkeypatch.setattr(m, 'download_candidate', download)
    monkeypatch.setattr(m, 'select_free', lambda rows, topic: rows[:5])
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'status': 'queued'}
    m.discover(job_id, m.DiscoverRequest(topic='funny cats', candidate_count=8))
    job = m.jobs[job_id]
    assert job['status'] == 'done' and len(job['clips']) == 5
    assert job['youtube_fallback'] and len(searches) == 1
    assert job['source_stats']['YouTube']['downloaded'] == 5
    assert sum('tiktok' in url for url in downloaded) == min(initial_count, 2)
    assert len(job['search_results']) == initial_count + 5
    assert 'opaque-session-secret' not in str(job)


def test_youtube_off_means_no_fallback_even_when_sources_fail(isolated, monkeypatch):
    monkeypatch.setattr(m, 'public_search', lambda *args: (results(), []))
    monkeypatch.setattr(m, 'youtube_search', lambda *args: pytest.fail('YouTube was disabled'))
    monkeypatch.setattr(m, 'download_candidate', lambda *args: (_ for _ in ()).throw(ValueError('HTTP 403')))
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'status': 'queued'}
    m.discover(job_id, m.DiscoverRequest(topic='funny cats', allow_youtube=False))
    assert m.jobs[job_id]['status'] == 'failed' and not m.jobs[job_id]['youtube_fallback']


def test_bad_social_scenes_trigger_youtube_and_canonical_duplicates_are_not_downloaded(isolated, monkeypatch):
    primary = results(5) + youtube_results(1)
    monkeypatch.setattr(m, 'public_search', lambda *args: (primary, []))
    extra = youtube_results(6)
    extra[0]['url'] = 'https://www.youtube.com/watch?v=CATCLIP0000'
    monkeypatch.setattr(m, 'youtube_search', lambda *args: (extra, []))
    calls = []
    def download(item):
        calls.append(item['url'])
        return {'id': uuid.uuid4().hex, 'name': item['title'], 'source': item['source'], 'source_url': item['url'], 'duration': 4}
    monkeypatch.setattr(m, 'download_candidate', download)
    def select(rows, topic):
        clips = [row for row in rows if row['source'] == 'YouTube']
        if len(clips) < 5:
            raise ValueError('Social scenes unusable')
        return clips[:5]
    monkeypatch.setattr(m, 'select_free', select)
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'status': 'queued'}
    m.discover(job_id, m.DiscoverRequest(topic='funny cats'))
    assert m.jobs[job_id]['status'] == 'done' and m.jobs[job_id]['youtube_fallback']
    assert len(calls) == len({m.canonical_url(url) for url in calls}) == 11


def test_no_youtube_round_when_five_social_moments_are_ready(isolated, monkeypatch):
    monkeypatch.setattr(m, 'public_search', lambda *args: (results(), []))
    monkeypatch.setattr(m, 'download_candidate', lambda item: {'id': uuid.uuid4().hex, 'source': 'TikTok'})
    monkeypatch.setattr(m, 'select_free', lambda rows, topic: rows[:5])
    monkeypatch.setattr(m, 'youtube_search', lambda *args: pytest.fail('Unnecessary YouTube round'))
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'status': 'queued'}
    m.discover(job_id, m.DiscoverRequest(topic='funny cats'))
    assert m.jobs[job_id]['status'] == 'done' and not m.jobs[job_id]['youtube_fallback']


def test_direct_youtube_search_filters_long_live_unrelated_and_duplicate_results(monkeypatch):
    import json
    rows = [{'id': 'CATCLIP0000', 'title': 'Funny cats jumping', 'duration': 30},
            {'id': 'CATCLIP0000', 'title': 'Funny cats duplicate', 'duration': 30},
            {'id': 'CATCLIP0001', 'title': 'Funny cats long', 'duration': 200},
            {'id': 'CATCLIP0002', 'title': 'Funny cats live', 'live_status': 'is_live'},
            {'id': 'CATCLIP0003', 'title': 'Football skills', 'duration': 20},
            {'id': '../../bad', 'title': 'Funny cats', 'duration': 20}]
    commands = []
    monkeypatch.setattr(m, 'run', lambda args, timeout: commands.append(args) or json.dumps({'entries': rows}).encode())
    def engines(topic, allow_youtube, limit, only_youtube=False):
        assert only_youtube is True
        return [youtube_results(2)[1]], []
    monkeypatch.setattr(f, 'public_search', engines)
    entries, warnings = f.youtube_search('funny cats', 8)
    assert len(entries) == 2 and not warnings
    assert entries[0]['url'] == 'https://www.youtube.com/watch?v=CATCLIP0000'
    assert '--flat-playlist' in commands[0] and commands[0][-1] == 'ytsearch8:funny cats shorts'
