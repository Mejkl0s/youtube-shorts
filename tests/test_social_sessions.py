from pathlib import Path
import stat
import time

import pytest
from fastapi.testclient import TestClient
from yt_dlp.cookies import YoutubeDLCookieJar

from backend import main as m
from backend import social_sessions as s


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    (tmp_path/'media').mkdir()
    monkeypatch.setattr(m, 'DATA', tmp_path)
    monkeypatch.delenv('STUDIO_PASSWORD', raising=False)
    monkeypatch.delenv('STUDIO_PUBLIC', raising=False)
    return tmp_path


def cookies(domain, value='opaque-test-session'):
    return ('# Netscape HTTP Cookie File\n#HttpOnly_.'+domain+'\tTRUE\t/\tTRUE\t'+str(int(time.time())+86400)+'\tsessionid\t'+value+'\n').encode()


def test_owner_only_import_filters_domains_and_stores_outside_media(isolated, monkeypatch):
    monkeypatch.setenv('STUDIO_PASSWORD', 'owner-test-password')
    client = TestClient(m.app)
    assert client.get('/api/source-sessions').status_code == 401
    assert client.post('/api/source-sessions/instagram', files={'file': ('cookies.txt', cookies('instagram.com'))}).status_code == 401
    auth = ('owner', 'owner-test-password')
    raw = cookies('instagram.com') + cookies('tiktok.com', 'another-platform-token')
    response = client.post('/api/source-sessions/instagram', files={'file': ('cookies.txt', raw)}, auth=auth)
    assert response.status_code == 200 and response.json() == {'configured': True, 'cookie_count': 1}
    path = isolated/'private/source-sessions/instagram.txt'
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert b'another-platform-token' not in path.read_bytes()
    state = client.get('/api/source-sessions', auth=auth)
    assert 'opaque-test-session' not in state.text
    assert not list((isolated/'media').iterdir())
    assert client.get('/private/source-sessions/instagram.txt', auth=auth).status_code == 404
    assert client.get('/api/source-sessions/instagram', auth=auth).status_code == 404
    assert client.delete('/api/source-sessions/instagram').status_code == 401
    assert client.delete('/api/source-sessions/instagram', auth=auth).json()['configured'] is False
    assert not path.exists()


def test_bad_or_expired_import_preserves_previous_session_and_never_echoes_values(isolated):
    client = TestClient(m.app)
    assert client.post('/api/source-sessions/tiktok', files={'file': ('cookies.txt', cookies('tiktok.com'))}).status_code == 200
    path = isolated/'private/source-sessions/tiktok.txt'
    original = path.read_bytes()
    invalid = [b'{"sessionid":"do-not-echo"}', cookies('evil.example', 'do-not-echo'), b'.tiktok.com\tTRUE\t/\tTRUE\t1\tsessionid\tdo-not-echo\n']
    for raw in invalid:
        response = client.post('/api/source-sessions/tiktok', files={'file': ('cookies.txt', raw)})
        assert response.status_code == 400 and 'do-not-echo' not in response.text
        assert path.read_bytes() == original
    assert client.post('/api/source-sessions/tiktok', files={'file': ('cookies.txt', b'x'*(s.MAX_COOKIES+1))}).status_code == 413
    assert client.post('/api/source-sessions/youtube', files={'file': ('cookies.txt', cookies('tiktok.com'))}).status_code == 404


def test_actual_cookie_jar_and_disposable_copy_are_scoped_and_cleaned(isolated):
    client = TestClient(m.app)
    client.post('/api/source-sessions/instagram', files={'file': ('cookies.txt', cookies('instagram.com'))})
    temporary = None
    with pytest.raises(RuntimeError):
        with s.download_session('https://www.instagram.com/reel/cats/') as path:
            temporary = path
            jar = YoutubeDLCookieJar(str(path))
            jar.load()
            assert 'opaque-test-session' in jar.get_cookie_header('https://www.instagram.com/reel/cats/')
            assert not jar.get_cookie_header('https://www.youtube.com/watch?v=CATCLIP0000')
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            raise RuntimeError('Download failed')
    assert temporary is not None and not temporary.exists()
    with s.download_session('https://www.youtube.com/watch?v=CATCLIP0000') as path:
        assert path is None
    with s.download_session('https://www.tiktok.com/@a/video/123') as path:
        assert path is None


def test_downloader_uses_matching_cookie_file_and_node_but_never_social_cookies_for_youtube(isolated, monkeypatch):
    client = TestClient(m.app)
    for provider, domain in [('tiktok', 'tiktok.com'), ('instagram', 'instagram.com')]:
        client.post('/api/source-sessions/'+provider, files={'file': ('cookies.txt', cookies(domain, provider+'-test-session'))})
    inspected = []
    def download(args, timeout):
        assert '--ignore-config' in args and '--no-remote-components' in args
        assert args[args.index('--js-runtimes')+1] == 'node'
        if 'youtu' in args[-1]:
            assert '--cookies' not in args
        else:
            path = Path(args[args.index('--cookies')+1])
            assert path.exists()
            content = path.read_text()
            provider = s.provider_for_url(args[-1])
            assert provider+'-test-session' in content
            assert ('instagram' if provider == 'tiktok' else 'tiktok')+'-test-session' not in content
            inspected.append(path)
        Path(args[args.index('-o')+1].replace('%(ext)s', 'mp4')).write_bytes(b'video-fixture')
        return b''
    monkeypatch.setattr(m, 'run', download)
    monkeypatch.setattr(m, 'register', lambda path, identity, title, **kwargs: {'id': identity, 'name': title, 'duration': 5})
    for url in ['https://www.tiktok.com/@a/video/123', 'https://www.instagram.com/reel/cats/', 'https://www.youtube.com/shorts/CATCLIP0000']:
        result = m.download_candidate({'url': url, 'title': 'Funny cats'})
        assert result['source_url'] == url
    assert len(inspected) == 2 and all(not path.exists() for path in inspected)
