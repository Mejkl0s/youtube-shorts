"""Exact source-file identity, independent of a video's public URL."""
import hashlib
import re
from .work_budget import checkpoint


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checkpoint()
            digest.update(chunk)
    return digest.hexdigest()


def original_hash(identity):
    from . import main as m
    seen = set()
    while identity not in seen and len(seen) < 10:
        seen.add(identity)
        meta = m.asset(identity)
        parent = meta.get('source_asset_id')
        if parent and parent != identity:
            identity = parent
            continue
        stored = meta.get('content_sha256', '')
        return stored if isinstance(stored,str) and re.fullmatch(r'[a-f0-9]{64}', stored) else file_hash(m.DATA/'media'/identity/'source')
    raise ValueError('Původní zdroj má neplatnou návaznost.')
