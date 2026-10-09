"""Download official Piper models, keeping TLS and manifest verification enabled."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
MODELS = Path(os.environ.get('PIPER_MODEL_DIR', str(ROOT / '.runtime/models')))
MANIFEST = {
    'en': {
        'name': 'en_US-lessac-medium',
        'path': 'en/en_US/lessac/medium/',
        'files': {
            '.onnx': (63201294, '2fc642b535197b6305c7c8f92dc8b24f'),
            '.onnx.json': (7010, '46e565a656f76b42b588d822025ed439'),
            'MODEL_CARD': (351, '42f2dd4a98149e12fc70b301d9579dfd'),
        },
    },
    'cs': {
        'name': 'cs_CZ-jirka-medium',
        'path': 'cs/cs_CZ/jirka/medium/',
        'files': {
            '.onnx': (63201294, 'da2deb0a3f93226a3f9b6e40d43c46ca'),
            '.onnx.json': (5025, '2762e45c5b084694093c683a5da7cf94'),
            'MODEL_CARD': (281, '85a220211eadd9b89f3dc023d82966b4'),
        },
    },
}
# Official release manifest: https://github.com/rhasspy/piper/blob/master/src/python_run/piper/voices.json
# Expected lengths and MD5 digests above come from that publisher manifest.


def verified(path, size, digest):
    return path.exists() and path.stat().st_size == size and hashlib.md5(path.read_bytes()).hexdigest() == digest


def download(language):
    info = MANIFEST[language]
    MODELS.mkdir(parents=True, exist_ok=True)
    for suffix, (size, digest) in info['files'].items():
        remote = suffix if suffix == 'MODEL_CARD' else info['name'] + suffix
        local = MODELS / (info['name'] + '.MODEL_CARD' if suffix == 'MODEL_CARD' else remote)
        if verified(local, size, digest):
            print(f'Already verified: {local.name}')
            continue
        url = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/' + info['path'] + remote
        temp = local.with_suffix(local.suffix + '.part')
        try:
            with urllib.request.urlopen(url, timeout=60) as response, temp.open('wb') as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            if not verified(temp, size, digest):
                raise ValueError(f'Publisher checksum or length mismatch: {remote}')
            temp.replace(local)
            print(f'Downloaded and verified: {local.name}')
        finally:
            temp.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--language', choices=['en', 'cs', 'all'], default='en')
    args = parser.parse_args()
    try:
        for language in MANIFEST if args.language == 'all' else [args.language]:
            download(language)
    except Exception as error:
        print(f'Voice model installation blocked: {error}', file=sys.stderr)
        print('Allow Hugging Face and its model CDN domains in environment settings. No TLS or checksum bypass is used.', file=sys.stderr)
        sys.exit(1)
