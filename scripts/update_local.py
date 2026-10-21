"""Update an existing local studio from a pinned repository commit, preserving user data."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import stat
import tempfile
from urllib.request import urlopen
import uuid
import zipfile

ROOT_FILES = {
    'package.json', 'package-lock.json', 'requirements.txt', 'index.html',
    'tsconfig.json', 'tsconfig.app.json', 'tsconfig.node.json', 'vite.config.ts',
    'SPUSTIT-WINDOWS.bat', 'OVERIT-WINDOWS.bat', 'WINDOWS.md', 'README.md',
}


def source_files(bundle: bytes, commit: str):
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Aktualizace vyzaduje presny identifikator verze.')
    prefix = f'youtube-shorts-{commit}'
    files, seen, total = {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        for member in archive.infolist():
            parts = PurePosixPath(member.filename).parts
            if (not parts or parts[0] != prefix or any(part in ('.', '..') for part in parts)
                    or '\\' in member.filename or any(':' in part for part in parts) or PurePosixPath(member.filename).is_absolute()
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError('Archiv obsahuje nepodporovanou cestu.')
            if member.is_dir() or len(parts) < 2:
                continue
            relative = PurePosixPath(*parts[1:])
            if not (str(relative) in ROOT_FILES or relative.parts[0] in ('backend', 'src', 'public', 'scripts')):
                continue
            if any(part.startswith('.') for part in relative.parts):
                continue
            identity = str(relative).casefold()
            if identity in seen or member.file_size > 5*1024*1024:
                raise ValueError('Archiv obsahuje duplicitni nebo prilis velky soubor.')
            seen.add(identity)
            total += member.file_size
            if total > 40*1024*1024 or len(files) >= 1000:
                raise ValueError('Archiv aktualizace je prilis velky.')
            files[relative] = archive.read(member)
    required = {'backend/main.py', 'backend/free_search.py', 'src/main.tsx', 'scripts/local_studio.py',
                'SPUSTIT-WINDOWS.bat', 'requirements.txt', 'package.json', 'package-lock.json'}
    if not required <= {str(path) for path in files}:
        raise ValueError('Archiv neobsahuje celou aplikaci.')
    return files


def ensure_regular(root: Path, relative: PurePosixPath):
    target = root
    for part in relative.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError('Aktualizace nepodporuje odkazy v cestach aplikace.')
    if target.exists() and not target.is_file():
        raise ValueError('Cil aktualizace neni bezny soubor.')
    return target


def install(root: Path, files, commit: str):
    root = root.resolve()
    if not (root/'SPUSTIT-WINDOWS.bat').is_file() or not (root/'backend').is_dir():
        raise ValueError('Nebyla nalezena existujici slozka Rank Studia.')
    if (root/'.runtime').is_symlink() or (root/'.runtime/update-backups').is_symlink():
        raise ValueError('Slozka dat nesmi byt odkaz.')
    targets = {relative: ensure_regular(root, relative) for relative in files}
    backup = root/'.runtime/update-backups'/uuid.uuid4().hex
    backup.mkdir(parents=True)
    existed = set()
    for relative, target in targets.items():
        if target.exists():
            saved = backup/str(relative)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            existed.add(relative)
    (backup/'update.json').write_text(json.dumps({'commit': commit, 'files': [str(p) for p in files]}), encoding='utf-8')
    changed = []
    try:
        for relative, data in files.items():
            target = targets[relative]
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix='.rank-update-', dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(data)
            try:
                os.replace(temporary, target)
                changed.append(relative)
            finally:
                temporary.unlink(missing_ok=True)
    except Exception:
        for relative in reversed(changed):
            target = targets[relative]
            if relative in existed:
                shutil.copy2(backup/str(relative), target)
            else:
                target.unlink(missing_ok=True)
        raise
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--ref', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-f0-9]{40}', args.ref):
        raise ValueError('Neplatna verze aktualizace.')
    try:
        with socket.create_connection(('127.0.0.1', 8765), timeout=1):
            raise ValueError('Nejdrive ukonci bezici studio v jeho cernem okne pomoci Ctrl+C a spust aktualizaci znovu.')
    except OSError:
        pass
    url = f'https://codeload.github.com/Mejkl0s/youtube-shorts/zip/{args.ref}'
    with urlopen(url, timeout=30) as response:
        bundle = response.read(45*1024*1024+1)
    if len(bundle) > 45*1024*1024:
        raise ValueError('Archiv aktualizace je prilis velky.')
    backup = install(args.root, source_files(bundle, args.ref), args.ref)
    print('Aktualizovano. Videa, relace, .env a Python prostredi zustaly zachovane.')
    print('Zaloha zdrojovych souboru:', backup)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Aktualizace se nezadarila:', error)
        raise SystemExit(1)
