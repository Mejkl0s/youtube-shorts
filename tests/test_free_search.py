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


def test_tiktok_cannot_starve_other_sources_and_video_queries_avoid_profiles(monkeypatch):
    calls = []
    def search(query, engine):
        calls.append(query)
        if 'site:tiktok.com' in query:
            assert 'inurl:video' in query
            return results(20)
        if 'site:instagram.com' in query:
            return [{'url': f'https://www.instagram.com/reel/cats{i}/', 'title': 'Funny cats'} for i in range(20)]
        return youtube_results(20)
    monkeypatch.setattr(f, 'engine_results', search)
    entries, warnings = f.public_search('funny cats', True, 12)
    assert len(entries) == len({m.canonical_url(row['url']) for row in entries}) == 12
    assert {row['source'] for row in entries} == {'TikTok', 'Instagram'}
    assert sum(row['source'] == 'Instagram' for row in entries) == 6
    assert any('site:instagram.com' in query for query in calls)
    assert any('site:youtube.com' in query for query in calls)
    assert not warnings


def test_topical_instagram_snippet_survives_generic_title_and_nested_markup(monkeypatch):
    parser = f.DuckResults()
    parser.feed('<a class="result__a" href="https://www.instagram.com/reel/snow123/">Instagram</a>'
                '<a class="result__snippet">The funniest <b>winter fails</b> in the snow.</a>'
                '<a class="result__a" href="https://www.instagram.com/reel/food123/">Instagram</a>'
                '<div class="result__snippet">Delicious <span>pasta</span> recipes.</div>')
    assert parser.results[0]['description'] == 'The funniest winter fails in the snow.'
    assert parser.results[1]['description'] == 'Delicious pasta recipes.'
    monkeypatch.setattr(f, 'engine_results', lambda *args: parser.results)
    entries, _ = f.public_search('winter fails', False, 8)
    assert [row['url'] for row in entries] == ['https://www.instagram.com/reel/snow123/']


@pytest.mark.parametrize('title', [
    'Antonio Vivaldi - Winter', 'Vivaldi: The Four Seasons - Fall and Winter',
    'Beautiful winter snow scenery', 'Funny kitchen fails', 'Winter failproof ski equipment',
])
def test_winter_fails_rejects_partial_topic_matches(title):
    assert f.relevance('winter fails', title) == 0


@pytest.mark.parametrize('title', [
    'Winter fail', 'Best winter fails compilation', 'Snow wipeouts',
    'Slipping on ice', 'Skiing crashes', 'Winter falls', '#winterfails', '#snowfails',
])
def test_winter_fails_accepts_subject_and_failed_action(title):
    assert f.relevance('winter fails', title) > 0


def test_required_subjects_cannot_be_replaced_by_generic_style_words():
    assert f.relevance('funny cats', 'Funny football moments') == 0
    assert f.relevance('funny cats', 'A cat jumping') > 0
    assert f.relevance('football skills', 'Football news') == 0
    assert f.relevance('football skills', 'Football skill compilation') > 0


def test_both_search_paths_reject_vivaldi_and_keep_winter_fails(monkeypatch):
    import json
    rows = [{'id': 'WINTER00001', 'title': 'Vivaldi - Winter', 'duration': 30},
            {'id': 'WINTER00002', 'title': 'Snow wipeouts', 'duration': 30}]
    monkeypatch.setattr(m, 'run', lambda *args: json.dumps({'entries': rows}).encode())
    monkeypatch.setattr(f, 'engine_results', lambda *args: [
        {'url': 'https://www.youtube.com/shorts/' + row['id'], 'title': row['title']}
        for row in rows])
    web, _ = f.public_search('winter fails', True, 8)
    direct, _ = f.youtube_search('winter fails', 8)
    assert [row['title'] for row in web] == ['Snow wipeouts']
    assert [row['title'] for row in direct] == ['Snow wipeouts']


@pytest.mark.parametrize(('detail', 'expected'), [
    ('Your IP address is blocked from accessing this post', 'blocked'),
    ('Unable to extract universal data for rehydration', 'extraction'),
    ('Requested format is not available', 'format'),
    ('[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed', 'tls'),
])
def test_download_failure_reports_known_causes_without_echoing_secrets(detail, expected):
    kind, reason = m.download_failure(RuntimeError(detail+' sessionid=opaque-owner-secret'))
    assert kind == expected
    assert 'opaque-owner-secret' not in reason


def test_failed_video_preparation_is_not_reported_as_download_block(isolated, monkeypatch):
    def download(args, timeout):
        (isolated/'media'/args[args.index('-o')+1].split('/')[-2]/'download.mp4').write_bytes(b'video fixture')
        return b''
    monkeypatch.setattr(m, 'run', download)
    monkeypatch.setattr(m, 'register', lambda *args: (_ for _ in ()).throw(RuntimeError('decoder failed; opaque-owner-secret')))
    with pytest.raises(m.CandidateDownloadError) as failure:
        m.download_candidate(results(1)[0])
    kind, reason = m.download_failure(failure.value)
    assert kind == 'processing' and 'Video se stáhlo' in reason
    assert 'opaque-owner-secret' not in reason
    assert not list((isolated/'media').iterdir())


@pytest.mark.parametrize(('output', 'expected'), [
    (b'[download] Winter fails does not pass filter (duration <= 600), skipping ..', 'duration'),
    (b'[download] File is larger than max-filesize (400000000 bytes > 314572800 bytes). Aborting.', 'size'),
])
def test_downloader_skip_reports_actual_limit_instead_of_generic_unavailable(isolated, monkeypatch, output, expected):
    def download(args, timeout):
        assert args[args.index('--match-filter')+1] == 'duration <= 600'
        assert args[args.index('--max-filesize')+1] == '300M'
        return output+b' private-session-token-do-not-echo'
    monkeypatch.setattr(m, 'run', download)
    with pytest.raises(m.CandidateDownloadError) as failure:
        m.download_candidate({'url': 'https://www.youtube.com/shorts/CATCLIP0000', 'title': 'Winter fails'})
    kind, reason = m.download_failure(failure.value)
    assert kind == expected and 'private-session-token' not in reason
    assert not list((isolated/'media').iterdir())


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
            m.ffmpeg('-i',str(source),'-vf',f'hue=h={len(downloads)*40}','-c:v','libx264',output)
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
    assert all(clip['source_start'] >= 2.9 and clip['source_start'] + clip['duration'] <= 6.05 for clip in job['clips'])
    assert all(clip['start'] == 0 and abs(clip['sourceDuration']-3) < .1 for clip in job['clips'])
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
            {'id': 'CATCLIP0001', 'title': 'Funny cats long', 'duration': 601},
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
    assert '--flat-playlist' in commands[0] and commands[0][-1] == 'ytsearch8:funny cats'


@pytest.mark.parametrize('unusable_extra', [False, True])
def test_partial_search_preserves_real_scenes_for_upload_completion_and_export(isolated, monkeypatch, unusable_extra):
    source = isolated/'moving.mp4'
    m.ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=160x284:r=12:d=3', '-c:v', 'libx264', str(source))
    black = isolated/'black.mp4'
    m.ffmpeg('-f', 'lavfi', '-i', 'color=black:s=160x284:r=12:d=3', '-c:v', 'libx264', str(black))
    entries = [{'url': f'https://www.instagram.com/reel/cats{i}/', 'title': f'Funny cats {i}'} for i in range(3 + int(unusable_extra))]
    monkeypatch.setattr(m, 'public_search', lambda *args: (entries, []))
    monkeypatch.setattr(m, 'ai_request', lambda *args, **kwargs: pytest.fail('Partial recovery called a paid API'))
    original = m.run
    def download(args, timeout=180):
        if 'yt_dlp' in args:
            output = args[args.index('-o')+1].replace('%(ext)s', 'mp4')
            index=int(args[-1].rsplit('cats',1)[1].strip('/'))
            m.ffmpeg('-i',str(black if index==3 else source),'-vf',f'hue=h={index*40}','-c:v','libx264',output)
            return b''
        return original(args, timeout)
    monkeypatch.setattr(m, 'run', download)
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'kind': 'discover', 'status': 'queued'}
    m.discover(job_id, m.DiscoverRequest(topic='funny cats'))
    client = TestClient(m.app)
    job = client.get('/api/jobs/'+job_id).json()
    assert job['status'] == 'failed' and job['youtube_fallback']
    assert '3/5 použitelných klipů' in job['message']
    clips = job['partial_clips']
    assert len(clips) == len({clip['id'] for clip in clips}) == 3
    assert job['candidate_count'] == 3 + int(unusable_extra)
    assert not job.get('clips') and not job.get('download')
    assert all(clip['voiceover'] == '' and clip['source_url'] in [row['url'] for row in entries[:3]] for clip in clips)
    assert all(0 <= clip['start'] < clip['start']+clip['duration'] <= 3.05 for clip in clips)
    assert client.post('/api/render', json={'title': 'TOP 5 CATS', 'clips': clips, 'voice': False}).status_code == 422
    if not unusable_extra:
        for index in range(2):
            upload = client.post('/api/upload', files={'file': (f'completion{index}.mp4', source.read_bytes(), 'video/mp4')})
            assert upload.status_code == 200, upload.text
            clips.append({**upload.json(), 'title': f'Extra cats {index}', 'voiceover': '', 'start': 0, 'duration': 3})
        render_id = uuid.uuid4().hex
        m.jobs[render_id] = {'id': render_id, 'status': 'queued'}
        m.render(render_id, m.Project(title='TOP 5 CATS', clips=clips, voice=False, resolution='720'))
        assert m.jobs[render_id]['status'] == 'done', m.jobs[render_id]
        assert client.get('/api/jobs/'+render_id+'/download').status_code == 200


def test_partial_ai_discovery_keeps_scenes_and_stops_later_assistant_actions(isolated, monkeypatch):
    from backend import assistant as a
    partial = [{'id': uuid.uuid4().hex, 'title': f'Funny cats {i}', 'voiceover': '', 'start': 0, 'duration': 3} for i in range(3)]
    assets = {clip['id']: {'id': clip['id'], 'name': clip['title'], 'duration': 3} for clip in partial}
    monkeypatch.setattr(m, 'asset', lambda identity: assets[identity])
    monkeypatch.setattr(a, 'plan_request', lambda body: a.Plan(reply='Připravím ranking.', actions=['discover', 'scripts', 'render']))
    def incomplete(child, body):
        assert body.mode == 'ai'
        m.set_job(child, status='failed', message='V editoru je zachováno 3/5 klipů.', partial_clips=partial)
    monkeypatch.setattr(m, 'discover', incomplete)
    monkeypatch.setattr(m, 'scripts', lambda *args: pytest.fail('Scripts ran after incomplete discovery'))
    monkeypatch.setattr(m, 'render', lambda *args: pytest.fail('Export ran after incomplete discovery'))
    job_id = uuid.uuid4().hex
    m.jobs[job_id] = {'id': job_id, 'kind': 'assistant', 'status': 'queued'}
    a.run_assistant(job_id, a.Request(message='Make a ranking', state=a.State(topic='funny cats')))
    job = m.jobs[job_id]
    assert job['status'] == 'failed' and not job.get('download')
    assert [clip['id'] for clip in job['project']['clips']] == [clip['id'] for clip in partial]
    assert job['project']['voice'] is False


def test_expanded_winter_search_finds_new_sources_without_music_or_repeats(monkeypatch):
    calls=[]
    def search(query,engine):
        calls.append(query)
        if 'site:tiktok.com' not in query:
            return []
        if query.startswith('snow fails'):
            return [
                {'url':'https://www.tiktok.com/@snow/video/500001','title':'Snow wipeouts'},
                {'url':'https://www.tiktok.com/@snow/video/500002','title':'Sledding fails'},
                {'url':'https://www.tiktok.com/@music/video/500003','title':'Antonio Vivaldi Winter'},
            ]
        return [{'url':'https://www.tiktok.com/@snow/video/500001?tracking=old','title':'Winter fails'}]
    monkeypatch.setattr(f,'engine_results',search)
    entries,_=f.public_search('ranking funniest winter fails',False,24,exclude_urls=['https://www.tiktok.com/@snow/video/500001'])
    assert [row['url'] for row in entries]==['https://www.tiktok.com/@snow/video/500002']
    assert any(q.startswith('snow fails') for q in calls)


def test_unavailable_engines_are_not_hammered_with_more_queries(monkeypatch):
    calls=[]
    def unavailable(query,engine):
        calls.append(engine)
        raise RuntimeError('HTTP 429 opaque-session-secret')
    monkeypatch.setattr(f,'engine_results',unavailable)
    entries,warnings=f.public_search('winter fails',True,40)
    assert not entries and sorted(calls)==['bing','duckduckgo']
    assert any('429' in warning for warning in warnings)
    assert 'opaque-session-secret' not in str(warnings)


def test_youtube_reads_beyond_used_sources_and_tries_related_queries(monkeypatch):
    import json
    commands=[]
    def search(args,timeout):
        commands.append(args)
        rows=[{'id':'WINTER00001','title':'Winter fails','duration':12}]
        if args[-1].endswith(':snow fails'):
            rows+=[{'id':'WINTER00002','title':'Snow wipeouts','duration':9},
                   {'id':'WINTER00003','title':'Vivaldi Winter','duration':20}]
        return json.dumps({'entries':rows}).encode()
    monkeypatch.setattr(m,'run',search)
    monkeypatch.setattr(f,'public_search',lambda *args,**kwargs:([],[]))
    entries,_=f.youtube_search('winter fails',8,['https://youtu.be/WINTER00001'])
    assert [row['url'] for row in entries]==['https://www.youtube.com/watch?v=WINTER00002']
    assert commands[0][-1]=='ytsearch9:winter fails'
    assert len(commands)<=4


def test_discovery_exclusions_are_enforced_even_if_provider_returns_old_urls(isolated,monkeypatch):
    entries=youtube_results(10)
    used=[row['url'] for row in entries[:5]]
    monkeypatch.setattr(m,'public_search',lambda *args:(entries,[]))
    downloaded=[]
    def download(item):
        downloaded.append(item['url'])
        return {'id':uuid.uuid4().hex,'source_url':item['url'],'source':'YouTube'}
    monkeypatch.setattr(m,'download_candidate',download)
    monkeypatch.setattr(m,'select_free',lambda rows,topic:rows[:5])
    job_id=uuid.uuid4().hex
    m.jobs[job_id]={'id':job_id,'status':'queued'}
    m.discover(job_id,m.DiscoverRequest(topic='funny cats',exclude_urls=used,blur_text=False))
    assert m.jobs[job_id]['status']=='done'
    assert set(downloaded)=={row['url'] for row in entries[5:]}
    assert not set(downloaded)&set(used)


def test_discovery_bounds_larger_candidate_pool_and_history(isolated,monkeypatch):
    monkeypatch.setattr(m.executor,'submit',lambda *args:None)
    client=TestClient(m.app)
    assert client.post('/api/discover',json={'topic':'winter fails','candidate_count':40}).status_code==202
    m.jobs.clear()
    assert client.post('/api/discover',json={'topic':'winter fails','candidate_count':1000}).status_code==422
    assert client.post('/api/discover',json={'topic':'winter fails','exclude_urls':['http://127.0.0.1/private']}).status_code==422


@pytest.mark.parametrize('direct_unavailable',[True,False])
def test_youtube_fallback_excludes_url_strings_after_repeated_search(monkeypatch,direct_unavailable):
    import json
    old='https://www.youtube.com/shorts/WINTER00001'
    first='https://www.youtube.com/watch?v=WINTER00002'
    extra='https://www.youtube.com/watch?v=WINTER00003'
    def direct(*args):
        if direct_unavailable:
            raise RuntimeError('HTTP 403')
        return json.dumps({'entries':[{'id':'WINTER00001','title':'Winter fails'},
                                      {'id':'WINTER00002','title':'Snow fails'}]}).encode()
    monkeypatch.setattr(m,'run',direct)
    # Exercise the REAL public_search and canonical_url fallback. A mock of
    # public_search would miss tuple identities accidentally passed as URLs.
    monkeypatch.setattr(f,'engine_results',lambda *args:[
        {'url':old,'title':'Winter fails'},
        {'url':first,'title':'Snow fails'},
        {'url':extra,'title':'Skiing crashes'}])
    entries,warnings=f.youtube_search('winter fails',8,[old])
    assert {m.canonical_url(row['url']) for row in entries}=={m.canonical_url(first),m.canonical_url(extra)}
    assert len(entries)==2
    assert bool(warnings)==direct_unavailable


def test_blocked_repeated_discovery_finishes_with_source_failure_not_tuple_crash(isolated,monkeypatch):
    monkeypatch.setattr(m,'public_search',lambda *args:(results(3),[]))
    monkeypatch.setattr(m,'youtube_search',f.youtube_search)
    monkeypatch.setattr(f,'engine_results',lambda *args:[])
    def blocked(*args,**kwargs):raise RuntimeError('HTTP 403')
    monkeypatch.setattr(m,'run',blocked)
    monkeypatch.setattr(m,'download_candidate',blocked)
    job_id=uuid.uuid4().hex;m.jobs[job_id]={'id':job_id,'status':'queued'}
    m.discover(job_id,m.DiscoverRequest(topic='winter fails',exclude_urls=['https://youtu.be/WINTER00001']))
    job=m.jobs[job_id]
    assert job['status']=='failed' and job['candidate_count']==0
    assert 'Podařilo se načíst jen 0 videí' in job['message']
    assert 'decode' not in job['message'] and 'tuple' not in str(job)
    assert job['youtube_fallback'] and job['partial_clips']==[]
    assert job['source_stats']['TikTok']['found']==3
    assert any(row['kind']=='blocked' for row in job['download_failures'])
