"""Owner login with signed, expiring cookies and legacy Basic API access."""
import base64
import hashlib
import hmac
import html
import os
from pathlib import Path
import secrets
import time
from urllib.parse import parse_qs, urlsplit

from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

COOKIE = 'rank_studio_session'
SESSION_SECONDS = 12 * 60 * 60


def credentials_match(username, candidate):
    valid = secrets.compare_digest(username.encode(), os.environ.get('STUDIO_USERNAME', 'owner').encode())
    return secrets.compare_digest(candidate.encode(), os.environ.get('STUDIO_PASSWORD', '').encode()) and valid


def session_signature(payload):
    key = hmac.new(os.environ['STUDIO_PASSWORD'].encode(),
                   ('rank-studio-session:' + os.environ.get('STUDIO_USERNAME', 'owner')).encode(), hashlib.sha256).digest()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def new_session():
    payload = f'{int(time.time()) + SESSION_SECONDS}.{secrets.token_hex(16)}'
    return payload + '.' + session_signature(payload)


def valid_session(token):
    if not token or len(token) > 200:
        return False
    try:
        expires, nonce, signature = token.split('.')
        payload = expires + '.' + nonce
        return int(expires) > time.time() and secrets.compare_digest(signature.encode(), session_signature(payload).encode())
    except (ValueError, UnicodeError):
        return False


def same_origin(request):
    origin = request.headers.get('origin')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        return False
    if not origin:
        return True  # Non-browser clients need no Origin header.
    try:
        parsed = urlsplit(origin)
        scheme = 'https' if os.environ.get('STUDIO_PUBLIC') == '1' else request.url.scheme
        return parsed.scheme == scheme and parsed.netloc == request.url.netloc
    except ValueError:
        return False


def login_page(username='owner', error=''):
    document = (Path(__file__).with_name('login.html')).read_text()
    document = document.replace('@@ERROR@@', '<p class="error" role="alert">' + html.escape(error) + '</p>' if error else '')
    document = document.replace('@@USERNAME@@', html.escape(username, quote=True))
    return HTMLResponse(document, headers={'Cache-Control': 'no-store', 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'", 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin'})


async def login(request):
    if request.method == 'GET':
        return login_page()
    if request.method != 'POST':
        return JSONResponse({'detail': 'Method not allowed'}, status_code=405)
    if not same_origin(request):
        return JSONResponse({'detail': 'Přihlášení musí proběhnout z tohoto webu.'}, status_code=403)
    if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
        return JSONResponse({'detail': 'Použijte přihlašovací formulář.'}, status_code=415)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 4096:
            return JSONResponse({'detail': 'Příliš dlouhý formulář.'}, status_code=413)
    try:
        fields = parse_qs(body.decode(), max_num_fields=4)
        username = fields.get('username', [''])[0]
        password = fields.get('password', [''])[0]
    except (ValueError, UnicodeError):
        return JSONResponse({'detail': 'Neplatný formulář.'}, status_code=400)
    if len(username) > 200 or len(password) > 512 or not credentials_match(username, password):
        return login_page(username[:200], 'Nesprávné jméno nebo heslo. Zkus to znovu.')
    response = RedirectResponse('/', status_code=303, headers={'Cache-Control': 'no-store'})
    response.set_cookie(COOKIE, new_session(), max_age=SESSION_SECONDS, httponly=True,
                        secure=request.url.scheme == 'https' or os.environ.get('STUDIO_PUBLIC') == '1', samesite='lax')
    return response


async def owner_access(request, call_next):
    if os.environ.get('RANK_LOCAL_MODE') == '1':
        if request.url.hostname not in ('127.0.0.1', 'localhost', '::1'):
            return JSONResponse({'detail': 'Lokální studio přijímá jen adresu tohoto počítače.'}, status_code=400)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not same_origin(request):
            return JSONResponse({'detail': 'Požadavek musí pocházet z lokálního studia.'}, status_code=403)
    if request.url.path == '/api/health':
        return await call_next(request)
    password = os.environ.get('STUDIO_PASSWORD', '')
    if not password:
        if os.environ.get('STUDIO_PUBLIC') == '1':
            return JSONResponse({'detail': 'Nastavte STUDIO_PASSWORD na hostingu, aby byl web přístupný pouze majiteli.'}, status_code=503)
        return await call_next(request)
    if request.url.path in ('/login', '/auth/login'):
        return await login(request)
    if request.url.path == '/auth/logout' and request.method == 'POST':
        if not same_origin(request):
            return JSONResponse({'detail': 'Odhlášení musí proběhnout z tohoto webu.'}, status_code=403)
        response = RedirectResponse('/', status_code=303, headers={'Cache-Control': 'no-store'})
        response.delete_cookie(COOKIE, httponly=True, samesite='lax', secure=request.url.scheme == 'https' or os.environ.get('STUDIO_PUBLIC') == '1')
        return response
    valid = valid_session(request.cookies.get(COOKIE))
    if not valid:
        try:
            scheme, encoded = request.headers.get('authorization', '').split(' ', 1)
            if scheme.lower() != 'basic':
                raise ValueError('Basic authentication required')
            username, candidate = base64.b64decode(encoded, validate=True).decode().split(':', 1)
            valid = credentials_match(username, candidate)
        except (ValueError, UnicodeError):
            valid = False
    if not valid:
        if request.method == 'GET' and request.url.path == '/':
            return login_page()
        # No browser-native challenge: embedded browsers can open /login normally.
        return JSONResponse({'detail': 'Přihlaste se do svého Rank Studia.', 'login_url': '/login'}, status_code=401,
                            headers={'Cache-Control': 'no-store'})
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and not same_origin(request):
        return JSONResponse({'detail': 'Požadavek musí pocházet z tohoto webu.'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response
