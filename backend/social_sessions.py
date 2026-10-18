"""Owner-only session imports; credentials never live under public media or in JSON."""
from contextlib import contextmanager
import os
import secrets
import time
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, UploadFile

router = APIRouter(prefix='/api/source-sessions')
PROVIDERS = {'tiktok': ('TikTok', 'tiktok.com'), 'instagram': ('Instagram', 'instagram.com')}
MAX_COOKIES = 256 * 1024


def provider_for_url(url):
    host = (urlparse(url).hostname or '').lower()
    return next((provider for provider, (_, domain) in PROVIDERS.items() if host == domain or host.endswith('.'+domain)), None)


def private_folder():
    from . import main as m
    path = m.DATA / 'private' / 'source-sessions'
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    path.parent.chmod(0o700)
    return path


def cookie_lines(content, provider):
    if provider not in PROVIDERS:
        raise ValueError('Nepodporovaný zdroj.')
    domain = PROVIDERS[provider][1]
    result = []
    for line in content.decode('utf-8-sig').splitlines():
        if not line.strip() or (line.startswith('#') and not line.startswith('#HttpOnly_')):
            continue
        parts = line.removeprefix('#HttpOnly_').split('\t')
        if len(parts) != 7:
            raise ValueError('Použij soubor cookies.txt ve formátu Netscape.')
        host, subdomains, path, secure, expires, name, value = parts
        host = host.lower().lstrip('.')
        if host != domain and not host.endswith('.'+domain):
            continue
        if any(ord(char) < 32 or ord(char) == 127 for part in parts for char in part):
            raise ValueError('Soubor obsahuje neplatné znaky.')
        if subdomains not in ('TRUE', 'FALSE') or secure not in ('TRUE', 'FALSE') or not path.startswith('/') or not name or len(name) > 256 or len(value) > 16000:
            raise ValueError('Neplatný soubor cookies.')
        try:
            expiry = int(expires or '0')
        except ValueError:
            raise ValueError('Neplatná platnost přihlášené relace.')
        if expiry < 0 or (expiry and expiry <= time.time()):
            continue
        result.append(line)
    if not result:
        raise ValueError('Soubor neobsahuje platné cookies pro vybranou síť. Exportuj aktuální relaci znovu.')
    return result


def status(provider):
    try:
        path = private_folder() / (provider + '.txt')
        if not path.is_file():
            return {'configured': False, 'cookie_count': 0}
        rows = cookie_lines(path.read_bytes(), provider)
        return {'configured': True, 'cookie_count': len(rows)}
    except (ValueError, UnicodeError, OSError):
        return {'configured': False, 'cookie_count': 0}


@router.get('')
def source_status():
    return {provider: status(provider) for provider in PROVIDERS}


@router.post('/{provider}')
async def import_session(provider: str, file: UploadFile):
    if provider not in PROVIDERS:
        raise HTTPException(404, 'Nepodporovaný zdroj.')
    content = bytearray()
    try:
        while chunk := await file.read(65536):
            content.extend(chunk)
            if len(content) > MAX_COOKIES:
                raise HTTPException(413, 'Soubor cookies může mít nejvýše 256 KB.')
        try:
            rows = cookie_lines(bytes(content), provider)
        except (ValueError, UnicodeError):
            raise HTTPException(400, 'Soubor musí obsahovat neprošlé cookies vybrané sítě ve formátu Netscape cookies.txt.')
        folder = private_folder()
        temporary = folder / (secrets.token_hex(16) + '.tmp')
        try:
            with open(temporary, 'xb', opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
                output.write(('# Netscape HTTP Cookie File\n'+'\n'.join(rows)+'\n').encode())
            os.replace(temporary, folder / (provider+'.txt'))
        finally:
            temporary.unlink(missing_ok=True)
        return status(provider)
    finally:
        await file.close()


@router.delete('/{provider}')
def remove_session(provider: str):
    if provider not in PROVIDERS:
        raise HTTPException(404, 'Nepodporovaný zdroj.')
    (private_folder() / (provider+'.txt')).unlink(missing_ok=True)
    return status(provider)


@contextmanager
def download_session(url):
    """A private disposable cookie jar is restricted to the matching social domain."""
    provider = provider_for_url(url)
    if not provider or not status(provider)['configured']:
        yield None
        return
    folder = private_folder()
    temporary = folder / (secrets.token_hex(16)+'.cookies')
    try:
        rows = cookie_lines((folder / (provider+'.txt')).read_bytes(), provider)
        with open(temporary, 'xb', opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
            output.write(('# Netscape HTTP Cookie File\n'+'\n'.join(rows)+'\n').encode())
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)
