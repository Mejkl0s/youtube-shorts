import io
from pathlib import PurePosixPath
import zipfile

import pytest

from scripts import update_local as u

COMMIT = 'a' * 40
REQUIRED = {'backend/main.py', 'backend/free_search.py', 'src/main.tsx', 'scripts/local_studio.py',
            'SPUSTIT-WINDOWS.bat', 'requirements.txt', 'package.json', 'package-lock.json'}


def bundle(extra=()):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        for name in REQUIRED:
            archive.writestr(f'youtube-shorts-{COMMIT}/{name}', 'new source')
        for name, content in extra:
            archive.writestr(name if name.startswith('/') else f'youtube-shorts-{COMMIT}/{name}', content)
    return out.getvalue()


def old_install(tmp_path):
    (tmp_path/'backend').mkdir()
    (tmp_path/'backend/main.py').write_text('original source')
    (tmp_path/'SPUSTIT-WINDOWS.bat').write_text('old launcher')
    for name in ('.env', '.runtime/media/retained.mp4', '.runtime/sessions/private.txt', '.venv/retained'):
        p = tmp_path/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('private retained data')
    return tmp_path


def test_pinned_update_keeps_user_files_and_backs_up_existing_sources(tmp_path):
    root = old_install(tmp_path)
    files = u.source_files(bundle([('.env', 'overwrite'), ('.runtime/media/retained.mp4', 'overwrite'),
                                   ('.venv/retained', 'overwrite')]), COMMIT)
    backup = u.install(root, files, COMMIT)
    assert (root/'backend/main.py').read_text() == 'new source'
    assert (backup/'backend/main.py').read_text() == 'original source'
    for name in ('.env', '.runtime/media/retained.mp4', '.runtime/sessions/private.txt', '.venv/retained'):
        assert (root/name).read_text() == 'private retained data'
    assert not list(root.rglob('.rank-update-*'))
    assert u.install(root, files, COMMIT) != backup


@pytest.mark.parametrize('name', ['../outside.py', '/outside.py', 'backend/../../outside.py',
                                  'backend\\outside.py', 'backend/secret:stream.py'])
def test_update_rejects_archive_paths_outside_the_source_tree(name):
    with pytest.raises(ValueError):
        u.source_files(bundle([(name, 'invalid')]), COMMIT)


def test_update_rolls_back_sources_after_failed_replace(tmp_path, monkeypatch):
    root = old_install(tmp_path)
    original = u.os.replace
    def fail_once(source, target):
        if target == root/'backend/failure.py':
            raise OSError('Simulated write failure')
        return original(source, target)
    monkeypatch.setattr(u.os, 'replace', fail_once)
    with pytest.raises(OSError, match='Simulated'):
        u.install(root, {PurePosixPath('backend/main.py'): b'new',
                         PurePosixPath('backend/new.py'): b'new',
                         PurePosixPath('backend/failure.py'): b'new'}, COMMIT)
    assert (root/'backend/main.py').read_text() == 'original source'
    assert not (root/'backend/new.py').exists()
    assert (root/'.runtime/media/retained.mp4').read_text() == 'private retained data'
    assert not list(root.rglob('.rank-update-*'))


def test_update_rejects_symlink_in_existing_source_directory(tmp_path):
    root = old_install(tmp_path)
    outside = tmp_path/'outside'
    outside.mkdir()
    (root/'src').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='odkazy'):
        u.install(root, {PurePosixPath('src/main.tsx'): b'new'}, COMMIT)
    assert not list(outside.iterdir())
