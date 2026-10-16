"""Password protection for the owner's hosted studio."""
import base64
import os
import secrets

from starlette.responses import JSONResponse


async def owner_access(request, call_next):
    # Hosting readiness reveals no credentials or project content.
    if request.url.path == '/api/health':
        return await call_next(request)
    password = os.environ.get('STUDIO_PASSWORD', '')
    if not password:
        if os.environ.get('STUDIO_PUBLIC') == '1':
            return JSONResponse({'detail': 'Set STUDIO_PASSWORD on the hosting service to protect your studio.'}, status_code=503)
        return await call_next(request)
    try:
        scheme, encoded = request.headers.get('authorization', '').split(' ', 1)
        if scheme.lower() != 'basic':
            raise ValueError('Basic authentication required')
        username, candidate = base64.b64decode(encoded, validate=True).decode().split(':', 1)
        valid = secrets.compare_digest(username.encode(), os.environ.get('STUDIO_USERNAME', 'owner').encode())
        valid = secrets.compare_digest(candidate.encode(), password.encode()) and valid
    except (ValueError, UnicodeError):
        valid = False
    if not valid:
        return JSONResponse({'detail': 'Sign in to your Short Story Studio.'}, status_code=401, headers={'WWW-Authenticate': 'Basic realm="Short Story Studio", charset="UTF-8"'})
    return await call_next(request)
