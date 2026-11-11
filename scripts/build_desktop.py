"""Reproducible native Windows NSIS build; Linux can validate the sidecar only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen
import zipfile

ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT/'build'
TOOLS=BUILD/'desktop-tools'
FFMPEG_VERSION='9.0.1'
FFMPEG_URL='https://github.com/GyanD/codexffmpeg/releases/download/9.0.1/ffmpeg-9.0.1-full_build.zip'
# microsoft/winget-pkgs/master/manifests/g/Gyan/FFmpeg/9.0.1/Gyan.FFmpeg.installer.yaml
FFMPEG_SHA256='2e8e28af97c2ae338ccef92e36da9b2a4cd21d0cad9dde093545606cb07f5b00'
COLLECT=('yt_dlp','yt_dlp_ejs','curl_cffi','piper','onnxruntime','edge_tts')


def run(args,**kwargs):
    print('Build:',Path(str(args[0])).name,' '.join(str(a) for a in args[1:4]),flush=True)
    return subprocess.run([str(a) for a in args],cwd=kwargs.pop('cwd',ROOT),check=True,**kwargs)


def digest(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()


def npm(*args):
    node=shutil.which('node');command=shutil.which('npm')
    if not node or not command:raise RuntimeError('Build potřebuje Node.js 24 a npm.')
    cli=(Path(command).parent/'node_modules/npm/bin/npm-cli.js') if os.name=='nt' else Path(command).resolve()
    if not cli.is_file():raise RuntimeError('Npm CLI nebylo nalezeno v oficiální instalaci Node.js.')
    run([node,cli,*args])


def prepare_tools():
    binary=TOOLS/'bin';binary.mkdir(parents=True,exist_ok=True)
    notices=TOOLS/'licenses';notices.mkdir(exist_ok=True)
    if os.name=='nt':
        archive=TOOLS/('ffmpeg-'+FFMPEG_VERSION+'.zip')
        if not archive.exists() or digest(archive)!=FFMPEG_SHA256:
            temporary=archive.with_suffix('.part')
            try:
                with urlopen(FFMPEG_URL,timeout=60) as source,temporary.open('wb') as target:
                    total=0
                    while chunk:=source.read(1024**2):
                        total+=len(chunk)
                        if total>1024**3:raise RuntimeError('Archiv FFmpeg překročil limit 1 GB.')
                        target.write(chunk)
                if digest(temporary)!=FFMPEG_SHA256:raise RuntimeError('SHA-256 archivu FFmpeg nesouhlasí; build zastaven.')
                temporary.replace(archive)
            finally:temporary.unlink(missing_ok=True)
        prefix='ffmpeg-'+FFMPEG_VERSION+'-full_build/'
        with zipfile.ZipFile(archive) as bundle:
            for name in ('ffmpeg.exe','ffprobe.exe'):
                with bundle.open(prefix+'bin/'+name) as source,(binary/name).open('wb') as target:shutil.copyfileobj(source,target)
            for member in bundle.namelist():
                if member.startswith(prefix) and Path(member).name.lower() in ('license','license.txt','readme.txt'):
                    (notices/('FFmpeg-'+Path(member).name)).write_bytes(bundle.read(member))
    else:
        for name in ('ffmpeg','ffprobe'):
            source=shutil.which(name)
            if not source:raise RuntimeError('Pro test sidecaru chybí '+name)
            if Path(source).resolve()!=(binary/name).resolve():shutil.copy2(source,binary/name)
    node=shutil.which('node')
    if not node:raise RuntimeError('Chybí Node.js pro yt-dlp JavaScript runtime.')
    major=int(subprocess.check_output([node,'-p','process.versions.node.split(".")[0]'],text=True).strip())
    if major<24:raise RuntimeError('Build vyžaduje Node.js 24 nebo novější.')
    node_target=binary/('node.exe' if os.name=='nt' else 'node')
    if Path(node).resolve()!=node_target.resolve():shutil.copy2(Path(node).resolve(),node_target)
    for name in ('LICENSE','LICENSE.txt'):
        license_file=Path(node).resolve().parent/name
        if license_file.is_file():shutil.copy2(license_file,notices/('Node-'+name))
    if not any(notices.glob('Node-*')):
        # Official Node license is public, no runtime network is needed afterward.
        version=subprocess.check_output([node,'--version'],text=True).strip()
        with urlopen(f'https://raw.githubusercontent.com/nodejs/node/{version}/LICENSE',timeout=30) as source:
            (notices/'Node-LICENSE').write_bytes(source.read(1024**2))
    (notices/'SOURCES.txt').write_text('FFmpeg source: https://ffmpeg.org/releases/ffmpeg-'+FFMPEG_VERSION+'.tar.xz\n'
        'Windows binaries and build configuration: '+FFMPEG_URL+'\nNode: https://nodejs.org/\n'
        'Python packages: requirements.txt; licenses collected into the sidecar by PyInstaller.\n',encoding='utf-8')
    return binary


def policy(signed=False):
    url=os.environ.get('RANK_UPDATE_URL','');publisher=os.environ.get('RANK_PUBLISHER','')
    signing=bool(os.environ.get('CSC_LINK') or os.environ.get('WIN_CSC_LINK') or os.environ.get('RANK_SIGNING_FROM_STORE')=='1')
    if signed and (not signing or not publisher):raise RuntimeError('Podepsaný build vyžaduje certifikát a RANK_PUBLISHER.')
    if url and not url.startswith('https://'):raise RuntimeError('Aktualizační zdroj musí být HTTPS.')
    if url:
        from urllib.parse import urlsplit
        parsed=urlsplit(url)
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RuntimeError('Aktualizační zdroj musí být veřejný HTTPS adresář bez přihlašovacích údajů v URL.')
    enabled=bool(url and publisher and signing)
    BUILD.mkdir(exist_ok=True)
    (BUILD/'update-policy.json').write_text(json.dumps({'enabled':enabled,'url':url,'publisher':publisher}),encoding='utf-8')
    return signing and bool(publisher)


def stage_ocr():
    """Use the distribution installed from the checksum-verified OCR installer."""
    source=Path(os.environ.get('RANK_OCR_SOURCE',''))
    if not os.environ.get('RANK_OCR_SOURCE') or not (source/'tesseract.exe').is_file():
        raise RuntimeError('Windows build potřebuje RANK_OCR_SOURCE z ověřené instalace Tesseract 5.4.0.')
    if not (source/'tessdata/eng.traineddata').is_file():
        raise RuntimeError('V OCR distribuci chybí anglická jazyková data.')
    target=TOOLS/'ocr'
    if target.exists():shutil.rmtree(target)
    target.mkdir(parents=True)
    for item in source.iterdir():
        if item.is_file() and (item.name=='tesseract.exe' or item.suffix.lower() in ('.dll','.txt','.md') or item.name.upper().startswith(('LICENSE','COPYING','NOTICE'))):
            shutil.copy2(item,target/item.name)
    (target/'tessdata').mkdir()
    for name in ('eng.traineddata','osd.traineddata'):
        if (source/'tessdata'/name).is_file():shutil.copy2(source/'tessdata'/name,target/'tessdata'/name)
    for name in ('configs','tessconfigs'):
        if (source/'tessdata'/name).is_dir():shutil.copytree(source/'tessdata'/name,target/'tessdata'/name)
    for name in ('doc','licenses'):
        if (source/name).is_dir():shutil.copytree(source/name,target/name)
    version=subprocess.check_output([str(target/'tesseract.exe'),'--version'],text=True,stderr=subprocess.STDOUT)
    if '5.4.0' not in version:raise RuntimeError('OCR distribuce není ověřená verze 5.4.0.')
    languages=subprocess.check_output([str(target/'tesseract.exe'),'--tessdata-dir',str(target/'tessdata'),'--list-langs'],text=True)
    if 'eng' not in languages.split():raise RuntimeError('Přibalené OCR nenačetlo jazyková data.')
    (target/'SOURCES.txt').write_text('Tesseract 5.4.0: https://github.com/tesseract-ocr/tesseract/tree/5.4.0\n'
        'Verified Windows distribution: https://github.com/UB-Mannheim/tesseract/releases/tag/v5.4.0.20240606\n'
        'Installer SHA-256: C885FFF6998E0608BA4BB8AB51436E1C6775C2BAFC2559A19B423E18678B60C9\n',encoding='utf-8')
    checks={item.relative_to(target).as_posix():digest(item) for item in target.rglob('*') if item.is_file()}
    (target/'SHA256SUMS.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    return target


def build_backend(binary):
    separator=';' if os.name=='nt' else ':'
    args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--console','--name','rank-backend',
          '--distpath',BUILD/'desktop-backend','--workpath',BUILD/'pyinstaller','--specpath',BUILD,
          '--paths',ROOT,'--add-data',str(ROOT/'dist')+separator+'dist',
          '--add-data',str(ROOT/'backend/fonts')+separator+'backend/fonts',
          '--add-data',str(TOOLS/'licenses')+separator+'licenses',
          '--hidden-import','scripts.download_models']
    if os.name=='nt':args.extend(['--add-data',str(stage_ocr())+separator+'ocr'])
    for package in COLLECT:args.extend(['--collect-all',package])
    for executable in binary.iterdir():args.extend(['--add-binary',str(executable)+separator+'bin'])
    args.append(ROOT/'scripts/desktop_backend.py');run(args)
    return BUILD/'desktop-backend/rank-backend'/('rank-backend.exe' if os.name=='nt' else 'rank-backend')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-install',action='store_true');parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--backend-only',action='store_true');parser.add_argument('--signed',action='store_true')
    args=parser.parse_args()
    if sys.version_info[:2]!=(3,12) or sys.maxsize<=2**32:raise SystemExit('Použij Python 3.12 x64.')
    if os.name!='nt' and not args.backend_only:raise SystemExit('Windows instalátor se sestavuje na Windows. --backend-only slouží k místnímu testu backendu.')
    signing=policy(args.signed);binary=prepare_tools()
    if args.prepare_only:print('Build tools:',binary);return
    if not args.skip_install:
        npm('ci','--no-audit','--no-fund');npm('--prefix','desktop','ci','--no-audit','--no-fund')
    npm('run','build');backend=build_backend(binary)
    if args.backend_only:print('Native sidecar:',backend);return
    environment=dict(os.environ)
    if signing:environment['RANK_SIGNED_BUILD']='1'
    run([shutil.which('node'),ROOT/'desktop/node_modules/electron-builder/cli.js','--config',ROOT/'desktop/builder.cjs','--win','nsis','--x64','--publish','never'],cwd=ROOT/'desktop',env=environment)
    output=ROOT/'release/windows';checks={p.name:digest(p) for p in output.glob('*') if p.is_file() and p.suffix in ('.exe','.yml','.blockmap')}
    if not any(name.endswith('.exe') for name in checks):raise RuntimeError('Windows instalátor nebyl vytvořen.')
    (output/'SHA256SUMS.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print('Windows installer:',output)


if __name__=='__main__':main()
