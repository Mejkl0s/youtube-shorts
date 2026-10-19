import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import httpx
import pytest

from backend import main as m
from scripts import local_studio as launcher


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def test_local_launcher_starts_real_editor_and_keeps_media_after_restart(tmp_path):
    source = tmp_path/'clip.mp4'
    m.ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=160x284:r=12:d=3', '-c:v', 'libx264', str(source))
    runtime = tmp_path/"Local PC O'Brien [Windows], ž; files"
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    environment = {**os.environ, 'RANK_DATA_DIR': str(runtime), 'STUDIO_PASSWORD': '', 'STUDIO_PUBLIC': '1'}
    uploaded = None
    for cycle in range(2):
        server = subprocess.Popen([sys.executable, 'scripts/local_studio.py', '--skip-setup', '--no-browser', '--port', str(port)],
                                  cwd=launcher.ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
        try:
            with httpx.Client(base_url=base, timeout=10, trust_env=False) as client:
                ready = False
                deadline = time.monotonic()+20
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        pytest.fail('Local launcher exited: '+server.stdout.read().decode(errors='replace'))
                    try:
                        health = client.get('/api/health').json()
                        ready = health.get('studio') == 'rank-studio' and health.get('local_mode') is True
                    except (httpx.HTTPError, ValueError):
                        pass
                    if ready:
                        break
                    time.sleep(.1)
                assert ready, 'Local studio never became ready'
                assert client.get('/').status_code == 200
                assert client.get('/api/fonts/bold').content[:4] == b'\x00\x01\x00\x00'
                assert client.get('/api/health', headers={'Host': 'other.example'}).status_code == 400
                # A remote page must not be able to mutate this passwordless loopback app.
                forbidden = client.post('/api/source-sessions/tiktok',
                                        files={'file': ('cookies.txt', b'private-test-session')},
                                        headers={'Origin': 'https://other.example'})
                assert forbidden.status_code == 403
                if cycle == 0:
                    response = client.post('/api/upload', files={'file': ('winter.mp4', source.read_bytes(), 'video/mp4')})
                    assert response.status_code == 200, response.text
                    uploaded = response.json()
                assert client.get(uploaded['url']).status_code == 200
                assert client.get(uploaded['thumbnail']).status_code == 200
        finally:
            if server.poll() is None:
                if os.name == 'nt':
                    server.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
            if server.stdout:
                server.stdout.close()
        assert (runtime/'media'/uploaded['id']/'source').is_file()
        # The launcher must terminate its own child and release the port.
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', port))


def test_launcher_refuses_an_occupied_port_without_stopping_it():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(RuntimeError, match='obsazeny'):
            launcher.start(Path(sys.executable), port, False)
        assert listener.getsockname()[1] == port


def test_local_doctor_really_encodes_mp4_and_does_not_require_online_keys(tmp_path):
    environment = {**os.environ, 'RANK_DATA_DIR': str(tmp_path), 'OPENAI_API_KEY': '', 'ELEVENLABS_API_KEY': ''}
    result = subprocess.run([sys.executable, 'scripts/local_studio.py', '--skip-setup', '--doctor'],
                            cwd=launcher.ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'OK: skutecne MP4, H264/AAC' in result.stdout
    assert 'offline test nepotvrzuje' in result.stdout
