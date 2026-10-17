from types import SimpleNamespace

from fastapi.testclient import TestClient
from backend import access
from backend.main import app


def test_public_hosting_requires_owner_password(monkeypatch):
    monkeypatch.setenv('STUDIO_PUBLIC', '1')
    monkeypatch.delenv('STUDIO_PASSWORD', raising=False)
    client = TestClient(app)
    assert client.get('/api/health').status_code == 200
    assert client.post('/api/demo').status_code == 503
    assert client.get('/').status_code == 503


def test_password_protects_media_and_paid_ai_routes(monkeypatch):
    monkeypatch.setenv('STUDIO_PASSWORD', 'local-test-password')
    monkeypatch.setenv('STUDIO_USERNAME', 'owner')
    client = TestClient(app)
    assert client.get('/api/health').status_code == 200
    for path in ['/media/missing.mp4', '/api/fonts/bold']:
        assert client.get(path).status_code == 401
    assert client.post('/api/assistant', json={'message': 'test'}).status_code == 401
    assert client.get('/api/fonts/bold', auth=('owner', 'wrong')).status_code == 401
    good = client.get('/api/fonts/bold', auth=('owner', 'local-test-password'))
    assert good.status_code == 200
    bad = client.get('/api/fonts/bold', headers={'Authorization': 'Basic !invalid-base64'})
    assert bad.status_code == 401


def test_browser_gets_login_page_without_native_auth_challenge(monkeypatch):
    monkeypatch.setenv('STUDIO_PASSWORD', 'local-test-password')
    client = TestClient(app)
    response = client.get('/', headers={'Accept': 'text/html'})
    assert response.status_code == 200
    assert 'Přihlas se do svého studia' in response.text
    assert 'action="/auth/login"' in response.text
    assert 'WWW-Authenticate' not in response.headers
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/').status_code == 200
    assert client.get('/login').status_code == 200
    assert client.get('/media/private.mp4').status_code == 401
    assert client.post('/api/assistant', json={'message': 'test'}).status_code == 401


def test_login_cookie_unlocks_editor_assets_and_logout_revokes_browser_access(monkeypatch):
    monkeypatch.setenv('STUDIO_PASSWORD', 'local-test-password')
    monkeypatch.setenv('STUDIO_USERNAME', 'owner')
    monkeypatch.setenv('STUDIO_PUBLIC', '1')
    client = TestClient(app, base_url='https://studio.example')
    wrong = client.post('/auth/login', data={'username': 'owner', 'password': 'wrong'})
    assert wrong.status_code == 200 and 'Nesprávné jméno nebo heslo' in wrong.text
    assert access.COOKIE not in client.cookies
    response = client.post('/auth/login', data={'username': 'owner', 'password': 'local-test-password'}, follow_redirects=False)
    assert response.status_code == 303 and response.headers['location'] == '/'
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie
    assert 'Max-Age=43200' in cookie and 'local-test-password' not in cookie
    assert client.get('/api/fonts/bold').status_code == 200
    editor = client.get('/')
    assert editor.status_code == 200 and 'pět klipů, jeden vítěz' in editor.text
    logout = client.post('/auth/logout', follow_redirects=False)
    assert logout.status_code == 303 and access.COOKIE not in client.cookies
    assert client.get('/api/fonts/bold').status_code == 401


def test_tampered_expired_and_password_rotated_sessions_are_rejected(monkeypatch):
    monkeypatch.setenv('STUDIO_PASSWORD', 'local-test-password')
    monkeypatch.setenv('STUDIO_USERNAME', 'owner')
    monkeypatch.delenv('STUDIO_PUBLIC', raising=False)
    client = TestClient(app)
    client.post('/auth/login', data={'username': 'owner', 'password': 'local-test-password'})
    token = client.cookies[access.COOKIE]
    anonymous = TestClient(app)
    anonymous.cookies.set(access.COOKIE, token[:-1] + ('0' if token[-1] != '0' else '1'))
    assert anonymous.get('/api/fonts/bold').status_code == 401
    for malformed in ('invalid', '1.x.é', '0.x.signature', 'x' * 201):
        assert access.valid_session(malformed) is False
    clock = access.time
    monkeypatch.setattr(access, 'time', SimpleNamespace(time=lambda: clock.time() + access.SESSION_SECONDS + 1))
    assert client.get('/api/fonts/bold').status_code == 401
    monkeypatch.setattr(access, 'time', clock)
    assert client.get('/api/fonts/bold').status_code == 200
    monkeypatch.setenv('STUDIO_PASSWORD', 'rotated-local-test-password')
    assert client.get('/api/fonts/bold').status_code == 401


def test_cross_origin_login_logout_and_changes_are_rejected(monkeypatch):
    monkeypatch.setenv('STUDIO_PASSWORD', 'local-test-password')
    monkeypatch.setenv('STUDIO_USERNAME', 'owner')
    monkeypatch.setenv('STUDIO_PUBLIC', '1')
    client = TestClient(app, base_url='https://studio.example')
    credentials = {'username': 'owner', 'password': 'local-test-password'}
    assert client.post('/auth/login', data=credentials, headers={'Origin': 'https://other.example'}).status_code == 403
    assert client.post('/auth/login', data=credentials, headers={'Origin': 'null'}).status_code == 403
    assert client.post('/auth/login', data=credentials, headers={'Origin': 'http://studio.example'}).status_code == 403
    assert access.COOKIE not in client.cookies
    assert client.post('/auth/login', data=credentials, headers={'Origin': 'https://studio.example'}, follow_redirects=False).status_code == 303
    for route in ('/auth/logout', '/api/demo'):
        assert client.post(route, headers={'Origin': 'https://other.example'}).status_code == 403
    assert client.get('/api/fonts/bold').status_code == 200


def test_login_form_is_bounded_and_escapes_input(monkeypatch):
    monkeypatch.setenv('STUDIO_PASSWORD', 'local-test-password')
    client = TestClient(app)
    response = client.post('/auth/login', data={'username': '\"><script>alert(1)</script>@@ERROR@@', 'password': 'wrong'})
    assert '<script>' not in response.text and '&lt;script&gt;' in response.text
    assert 'value="&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;@@ERROR@@"' in response.text
    assert client.post('/auth/login', content='x' * 4097, headers={'Content-Type': 'application/x-www-form-urlencoded'}).status_code == 413
    assert client.post('/auth/login', json={'username': 'owner'}).status_code == 415
