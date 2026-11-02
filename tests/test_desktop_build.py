import hashlib
import os
from pathlib import Path
import zipfile

from scripts import build_desktop as build


def test_tool_preparation_can_repeat_after_staged_binaries_enter_path(tmp_path,monkeypatch):
    tools=tmp_path/'staged';origin=tmp_path/'original';origin.mkdir()
    binary=tools/'bin';licenses=tools/'licenses';licenses.mkdir(parents=True)
    (licenses/'Node-LICENSE').write_text('fixture license')
    names={name:name+('.exe' if os.name=='nt' else '') for name in ('node','ffmpeg','ffprobe')}
    for name,filename in names.items():(origin/filename).write_bytes(('fixture '+name).encode())
    monkeypatch.setattr(build,'TOOLS',tools)
    def which(name):
        filename=names.get(name)
        if not filename:return None
        return str((binary/filename) if (binary/filename).exists() else (origin/filename))
    monkeypatch.setattr(build.shutil,'which',which)
    monkeypatch.setattr(build.subprocess,'check_output',lambda *a,**kw:'24')
    if os.name=='nt':
        archive=tools/('ffmpeg-'+build.FFMPEG_VERSION+'.zip')
        with zipfile.ZipFile(archive,'w') as package:
            for name in ('ffmpeg','ffprobe'):
                package.writestr('ffmpeg-'+build.FFMPEG_VERSION+'-full_build/bin/'+names[name],(origin/names[name]).read_bytes())
        monkeypatch.setattr(build,'FFMPEG_SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
    assert build.prepare_tools()==binary
    before={path.name:path.read_bytes() for path in binary.iterdir()}
    assert build.prepare_tools()==binary
    assert {path.name:path.read_bytes() for path in binary.iterdir()}==before
