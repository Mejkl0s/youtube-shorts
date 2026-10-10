"""Public search and deterministic scene selection. No paid provider calls."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

import httpx
import numpy as np


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    parser = Text()
    parser.feed(str(value or '')[:6000])
    return ' '.join(' '.join(parser.parts).split())


def rss_results(content: str):
    if '<!DOCTYPE' in content.upper() or '<!ENTITY' in content.upper():
        raise ValueError('Nepodporovaný vyhledávací dokument.')
    root = ElementTree.fromstring(content)
    if root.tag != 'rss':
        raise ValueError('Vyhledávač nevrátil veřejné výsledky.')
    return [{'url': item.findtext('link', ''), 'title': plain(item.findtext('title', '')),
             'description': plain(item.findtext('description', ''))}
            for item in root.findall('./channel/item')[:30]]


class DuckResults(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'result__a' in attrs.get('class', '').split():
            href = attrs.get('href', '')
            # Decode the engine's destination parameter, never download its redirect URL.
            if href.startswith('//'):
                href = 'https:' + href
            parsed = urlparse(href)
            if parsed.hostname in ('duckduckgo.com', 'html.duckduckgo.com'):
                href = parse_qs(parsed.query).get('uddg', [''])[0]
            self.active = {'url': href, 'parts': []}

    def handle_data(self, data):
        if self.active is not None:
            self.active['parts'].append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            self.results.append({'url': self.active['url'], 'title': plain(' '.join(self.active['parts'])), 'description': ''})
            self.active = None


def engine_results(query: str, engine: str):
    endpoint = 'https://www.bing.com/search' if engine == 'bing' else 'https://html.duckduckgo.com/html/'
    params = {'q': query, 'format': 'rss', 'count': '20'} if engine == 'bing' else {'q': query}
    # Read a bounded public response. Captchas/login/rate limits are reported, never bypassed.
    with httpx.Client(timeout=10, follow_redirects=False, headers={'User-Agent': 'Mozilla/5.0 (compatible; RankStudio/1.0)'}) as client:
        with client.stream('GET', endpoint, params=params) as response:
            if response.status_code != 200:
                raise ValueError(f'Veřejný vyhledávač {engine} není dostupný (HTTP {response.status_code}).')
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 2 * 1024 * 1024:
                    raise ValueError('Vyhledávací odpověď je příliš velká.')
    text = content.decode('utf-8', errors='replace')
    if engine == 'bing':
        return rss_results(text)
    parser = DuckResults()
    parser.feed(text)
    if not parser.results:
        raise ValueError('Veřejné výsledky nejsou dostupné; může jít o omezení vyhledávače.')
    return parser.results[:30]


def tokens(value):
    ignored = {'the', 'and', 'best', 'top', 'video', 'videos', 'clip', 'clips', 'tiktok', 'instagram', 'youtube', 'shorts', 'reels', 'na', 'a', 'z', 'klipy', 'videa', 'pet', 'pět'}
    return {word for word in re.findall(r'[^\W_]+', value.casefold()) if len(word) > 2 and word not in ignored}


def relevance(topic, title, description=''):
    wanted = tokens(topic)
    found = tokens(title + ' ' + description)
    if not wanted:
        return 0.0
    matched = {word for word in wanted if any(word == other or (len(word) >= 4 and other.startswith(word)) for other in found)}
    return len(matched) / len(wanted)


def public_search(topic: str, allow_youtube: bool, limit: int):
    from .main import canonical_url, social_url
    sources = [('TikTok', 'site:tiktok.com'), ('Instagram', 'site:instagram.com/reel/')]
    if allow_youtube:
        sources.append(('YouTube', 'site:youtube.com/shorts/'))
    entries, seen, warnings = [], set(), []
    for source, restriction in sources:
        for suffix in ('', ' moments'):
            query = topic + suffix + ' ' + restriction
            for engine in ('bing', 'duckduckgo'):
                added = 0
                try:
                    results = engine_results(query, engine)
                    for position, result in enumerate(results):
                        url = result['url']
                        if not social_url(url, allow_youtube) or len(url) > 500:
                            continue
                        host = urlparse(url).hostname
                        actual_source = 'TikTok' if host in ('tiktok.com', 'www.tiktok.com') else 'Instagram' if host in ('instagram.com', 'www.instagram.com') else 'YouTube'
                        if actual_source != source:
                            continue
                        identity = canonical_url(url)
                        if identity in seen:
                            continue
                        match = relevance(topic, result['title'], result.get('description', ''))
                        # No semantic AI assessment: require actual topical search text.
                        if match == 0:
                            continue
                        seen.add(identity)
                        entries.append({**result, 'url': url[:500], 'title': result['title'][:100] or topic,
                                        'search_score': match * .85 + .15 / (position + 1),
                                        'provider': engine, 'source': source})
                        added += 1
                        if len(entries) >= limit:
                            return entries[:limit], warnings
                except Exception:
                    warnings.append(f'{engine}: veřejné vyhledávání pro {source} nebylo dostupné.')
                if added:
                    break
    return entries, list(dict.fromkeys(warnings))


def window_score(raw: bytes):
    frames = np.frombuffer(raw, dtype=np.uint8)
    if frames.size < 64 * 64 * 2 or frames.size % (64 * 64):
        raise ValueError('Nedostatek skutečných snímků pro výběr scény.')
    frames = frames.reshape(-1, 64, 64).astype(np.float32)
    brightness = frames.mean(axis=(1, 2))
    if np.all((brightness < 3) | (brightness > 252)):
        return None
    motion = min(float(np.abs(np.diff(frames, axis=0)).mean()) / 24, 1)
    edges = min(float((np.abs(np.diff(frames, axis=1)).mean() + np.abs(np.diff(frames, axis=2)).mean()) / 32), 1)
    exposure = float(((brightness >= 10) & (brightness <= 245)).mean())
    return .4 * motion + .4 * edges + .2 * exposure


def select_free(candidates, topic):
    from . import main as m
    selected = []
    for candidate in candidates:
        path = m.DATA / 'media' / candidate['id'] / 'source'
        best = None
        try:
            for scene_start, scene_duration in m.scene_windows(path):
                duration = min(4.0, scene_duration)
                start = scene_start + max(0, (scene_duration - duration) / 2)
                raw = m.ffmpeg('-ss', str(start), '-i', str(path), '-t', str(duration), '-an',
                               '-vf', 'fps=3,scale=64:64,format=gray', '-f', 'rawvideo', 'pipe:1')
                score = window_score(raw)
                if score is not None and (best is None or score > best[0]):
                    best = (score, start, duration)
            if best is None:
                continue
            technical, start, duration = best
            selected.append((float(candidate.get('search_score', 0)) * .8 + technical * .2, candidate, start, duration))
        except Exception:
            continue
    # TikTok/Instagram remain primary. YouTube only fills missing positions.
    social = [row for row in selected if row[1].get('source') != 'YouTube']
    supplement = [row for row in selected if row[1].get('source') == 'YouTube']
    chosen = sorted(social, key=lambda row: row[0], reverse=True)[:5]
    chosen += sorted(supplement, key=lambda row: row[0], reverse=True)[:5-len(chosen)]
    if len(chosen) < 5:
        raise ValueError(f'Pouze {len(chosen)} dostupných videí obsahuje použitelnou souvislou scénu. Zkuste jiné téma nebo nahrajte vlastní klipy.')
    result = []
    for _, candidate, start, duration in sorted(chosen, key=lambda row: row[0]):
        result.append({**candidate, 'title': candidate['name'][:60], 'voiceover': '', 'start': start, 'duration': duration,
                       'sourceDuration': candidate['duration'],
                       'reason': 'Předběžný výběr podle shody textu s tématem, ostrosti a pohybu. Souvislý úsek bez detekovaného střihu; obsah a pořadí zkontroluj.'})
    return result
