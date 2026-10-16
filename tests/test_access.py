import base64

from fastapi.testclient import TestClient
from backend.main import app


def test_public_hosting_requires_owner_password(monkeypatch):
    monkeypatch.setenv('STUDIO_PUBLIC', '1')
    monkeypatch.delenv('STUDIO_PASSWORD', raising=False)
    client = TestClient(app)
    assert client.get('/api/health').status_code == 200
    assert client.post('/api/demo').status_code == 503
    assert client.get('/').status_code == 503
    assert client.get('/examples/story-narrated.mp4').status_code == 503


def test_password_protects_media_and_paid_ai_routes(monkeypatch):
    monkeypatch.setenv('STUDIO_PASSWORD', 'local-test-password')
    monkeypatch.setenv('STUDIO_USERNAME', 'owner')
    client = TestClient(app)
    assert client.get('/api/health').status_code == 200
    for path in ['/', '/media/missing.mp4', '/api/fonts/bold', '/examples/story-narrated.mp4']:
        assert client.get(path).status_code == 401
    assert client.post('/api/assistant', json={'message': 'test'}).status_code == 401
    assert client.get('/api/fonts/bold', auth=('owner', 'wrong')).status_code == 401
    good = client.get('/api/fonts/bold', auth=('owner', 'local-test-password'))
    assert good.status_code == 200
    bad = client.get('/', headers={'Authorization': 'Basic !invalid-base64'})
    assert bad.status_code == 401
