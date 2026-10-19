"""Prepare and start the same web studio on a personal computer (stdlib only)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent.parent


def fingerprint(paths):
    digest = hashlib.sha256()
    files = []
    for path in paths:
        files.extend(sorted(path.rglob('*')) if path.is_dir() else [path])
    for path in files:
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode('utf-8'))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def command(arguments):
    environment = os.environ.copy()
    environment.setdefault('PIP_CACHE_DIR', str(ROOT/'.runtime/cache/pip'))
    environment.setdefault('npm_config_cache', str(ROOT/'.runtime/cache/npm'))
    subprocess.run([str(arg) for arg in arguments], cwd=ROOT, env=environment, check=True)


def prepare(skip_setup=False):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError('Pouzij Python 3.12. Ve Windows spust SPUSTIT-WINDOWS.bat.')
    if not (ROOT/'backend/fonts/DejaVuSans-Bold.ttf').is_file():
        raise RuntimeError('Chybi pribaleny font. Rozbal cely archiv aplikace.')
    for tool in ('node', 'npm', 'ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            raise RuntimeError(f'Chybi {tool}. Ve Windows spust SPUSTIT-WINDOWS.bat; podrobnosti jsou ve WINDOWS.md.')
    node_major = int(subprocess.check_output(['node', '-p', 'process.versions.node.split(".")[0]'], text=True).strip())
    if node_major < 24:
        raise RuntimeError('Je potreba Node.js 24 nebo novejsi. Nainstaluj aktualni Node.js LTS.')
    python = ROOT/'.venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        if skip_setup:
            raise RuntimeError('Chybi .venv. Spust aplikaci bez --skip-setup.')
        print('Pripravuji Python prostredi...', flush=True)
        venv.EnvBuilder(with_pip=True).create(ROOT/'.venv')
    if not skip_setup:
        cache = ROOT/'.runtime/launcher'
        cache.mkdir(parents=True, exist_ok=True)
        dependency_hash = fingerprint([ROOT/'requirements.txt'])
        stamp = cache/'python.sha256'
        if not stamp.is_file() or stamp.read_text() != dependency_hash:
            command([python, '-m', 'pip', 'install', '-r', ROOT/'requirements.txt'])
            command([python, '-m', 'pip', 'check'])
            stamp.write_text(dependency_hash, encoding='utf-8')
        npm = shutil.which('npm')
        dependency_hash = fingerprint([ROOT/'package.json', ROOT/'package-lock.json'])
        stamp = cache/'node.sha256'
        if not (ROOT/'node_modules/.package-lock.json').is_file() or not stamp.is_file() or stamp.read_text() != dependency_hash:
            command([npm, 'ci'])
            stamp.write_text(dependency_hash, encoding='utf-8')
        build_hash = fingerprint([ROOT/name for name in ('src', 'public', 'index.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts')])
        stamp = cache/'frontend.sha256'
        if not (ROOT/'dist/index.html').is_file() or not stamp.is_file() or stamp.read_text() != build_hash:
            command([npm, 'run', 'build'])
            stamp.write_text(build_hash, encoding='utf-8')
    if not (ROOT/'dist/index.html').is_file():
        raise RuntimeError('Chybi sestaveny web. Spust aplikaci bez --skip-setup.')
    return python


def local_environment():
    environment = os.environ.copy()
    environment.update(RANK_LOCAL_MODE='1', STUDIO_PUBLIC='0', PYTHONUTF8='1')
    return environment


def start(python, port, open_browser=True):
    # Never reuse an unknown service or terminate somebody else's process.
    with socket.socket() as probe:
        # Unix keeps closed connections in TIME_WAIT. Match asyncio's Unix
        # listener semantics without enabling Windows' different port sharing.
        if os.name != 'nt':
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            raise RuntimeError(f'Port {port} je obsazeny. Zavri predchozi okno studia a spust ho znovu.') from None
    arguments = [str(python), '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', str(port), '--no-access-log']
    if (ROOT/'.env').is_file():
        arguments += ['--env-file', str(ROOT/'.env')]
    server = subprocess.Popen(arguments, cwd=ROOT, env=local_environment())
    base = f'http://127.0.0.1:{port}'
    # This opener is restricted to the loopback URL above, never an external host.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        deadline = time.monotonic()+45
        ready = False
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError('Server se nespustil. Konkretni chyba je uvedena nad touto zpravou.')
            try:
                with opener.open(base+'/api/health', timeout=1) as response:
                    health = json.load(response)
                ready = health.get('studio') == 'rank-studio' and health.get('local_mode') is True
            except (OSError, ValueError):
                pass
            if ready:
                break
            time.sleep(.2)
        if not ready:
            raise RuntimeError('Studio neodpovedelo do 45 sekund.')
        print('\nRank Studio bezi na TVEM POCITACI. Toto okno nech otevrene.', flush=True)
        print('Pokud se prohlizec neotevre, zadej do bezneho prohlizece: '+base, flush=True)
        print('Zastaveni: Ctrl+C. Dostupnost klipu over tematem winter fails.', flush=True)
        if open_browser:
            webbrowser.open(base)
        return server.wait()
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


def main():
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, stop)
    parser = argparse.ArgumentParser(description='Rank Studio na tomto pocitaci')
    parser.add_argument('--doctor', action='store_true', help='Otestovat lokalni nastroje a skutecne kodovani videa')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--skip-setup', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--port', type=int, default=8765)
    options = parser.parse_args()
    if not 1024 <= options.port <= 65535:
        parser.error('Port musi byt mezi 1024 a 65535.')
    try:
        python = prepare(options.skip_setup)
        if options.doctor:
            return subprocess.call([str(python), '-m', 'scripts.local_check'], cwd=ROOT, env=local_environment())
        return start(python, options.port, not options.no_browser)
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, subprocess.CalledProcessError, OSError) as error:
        print('CHYBA: '+str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
