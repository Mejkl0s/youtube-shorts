"""Public search and deterministic scene selection. No paid provider calls."""
from __future__ import annotations

import re
import json
import sys
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
        self.snippet_tag = None
        self.snippet_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.results and 'result__snippet' in attrs.get('class', '').split():
            self.snippet_tag = tag
            self.snippet_parts = []
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
        if self.snippet_tag:
            self.snippet_parts.append(data)

    def handle_endtag(self, tag):
        if tag == self.snippet_tag:
            self.results[-1]['description'] = plain(' '.join(self.snippet_parts))
            self.snippet_tag = None
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
    ignored = {'the', 'and', 'best', 'top', 'video', 'clip', 'tiktok', 'instagram', 'youtube', 'short', 'reel',
               'moment', 'compilation', 'ranking', 'na', 'a', 'z', 'klipy', 'videa', 'pet', 'pět'}
    words = set()
    for word in re.findall(r'[^\W_]+', value.casefold()):
        # Ordinary English plurals only; arbitrary prefixes (e.g. failproof)
        # must not count as a topical match.
        if word == 'falls':
            word = 'falling'
        elif word.endswith(('ches', 'shes', 'sses', 'xes', 'zes')):
            word = word[:-2]
        elif len(word) > 3 and word.endswith('s') and not word.endswith(('ss', 'us', 'is', 'ies')):
            word = word[:-1]
        if len(word) > 2 and word not in ignored:
            words.add(word)
    return words


WINTER_WORDS = frozenset({'winter', 'snow', 'snowy', 'ice', 'icy', 'ski', 'skiing', 'skier',
                          'sled', 'sledding', 'snowboard', 'snowboarding', 'snowboarder'})
FAIL_WORDS = frozenset({'fail', 'failed', 'failing', 'failure', 'blooper', 'wipeout', 'slip',
                       'slipped', 'slipping', 'fell', 'falling', 'crash', 'crashed', 'crashing'})
# A bare "fall" is ambiguous (also autumn, including Vivaldi's seasons).
COMPOUND_FAILS = frozenset(word + ending for word in WINTER_WORDS for ending in ('fail', 'fails'))


def relevance(topic, title, description=''):
    wanted = tokens(topic)
    found = tokens(title + ' ' + description)
    # Formatting/style words cannot replace the subject or action. Keep a
    # style word as a last resort when the query contains no concrete subject.
    subjects = wanted - {'funny', 'funniest', 'epic', 'amazing', 'insane'}
    wanted = subjects or wanted
    if not wanted:
        return 0.0
    if found & COMPOUND_FAILS:
        found.update({'winter', 'fail'})
    for word in wanted:
        aliases = WINTER_WORDS if word == 'winter' else FAIL_WORDS if word in FAIL_WORDS else {word}
        if not found & aliases:
            return 0.0
    # Every essential concept must be present. Partial overlap must never
    # admit music/scenery for "winter fails" just to fill the clip count.
    return 1.0


def search_topic(topic):
    """Keep the video title intact; search for its concrete topic instead."""
    words = re.findall(r"[^\W_]+", topic.casefold())
    ignored = {'ranking', 'rank', 'top', 'clip', 'clips', 'video', 'videos', 'moment', 'moments', 'compilation', 'compilations'}
    clean = ['funny' if word == 'funniest' else word for word in words if word not in ignored and not word.isdigit()]
    return ' '.join(clean) or topic


def query_variants(topic):
    """Expand concrete concepts, while relevance still checks the original topic."""
    base = search_topic(topic)
    queries = [base, base + ' compilation']
    wanted = tokens(topic)
    if 'winter' in wanted and wanted & FAIL_WORDS:
        queries += ['snow fails', 'slipping on ice fails', 'skiing crashes', 'sledding fails']
    else:
        queries += [base + ' moments', base + ' shorts']
    return list(dict.fromkeys(queries))


def search_warning(engine, source, error):
    # Do not echo response bodies, credentials, session data or raw process errors.
    status = re.search(r'\b(403|407|429|5\d\d)\b', str(error))
    reason = f' (HTTP {status[1]})' if status else ''
    return f'{engine}: veřejné vyhledávání pro {source} nebylo dostupné{reason}.'


def public_search(topic: str, allow_youtube: bool, limit: int, only_youtube: bool = False, exclude_urls=()):
    from .main import canonical_url, social_url
    sources = [('TikTok', 'site:tiktok.com inurl:video'), ('Instagram', 'site:instagram.com/reel/')]
    if allow_youtube:
        sources.append(('YouTube', 'site:youtube.com'))
    if only_youtube:
        sources = [source for source in sources if source[0] == 'YouTube']
    pools, seen, warnings, unavailable = [], {canonical_url(url) for url in exclude_urls}, [], set()
    for source, restriction in sources:
        entries = []
        for variant in query_variants(topic):
            if len(entries) >= limit:
                break
            query = variant + ' ' + restriction
            for engine in ('bing', 'duckduckgo'):
                if engine in unavailable:
                    continue
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
                            break
                except Exception as error:
                    warnings.append(search_warning(engine, source, error))
                    # A challenge, network refusal or timeout is not fixed by
                    # repeating the same request with more topic variants.
                    unavailable.add(engine)
                if added:
                    break
        pools.append(entries)
        if not entries:
            warnings.append(f'{source}: vyhledávače nevrátily žádný odpovídající odkaz na video.')
    # Search each enabled source before applying the total limit. Interleaving
    # reserves opportunities for Instagram even when TikTok fills its own pool.
    social_pools = pools if only_youtube else pools[:2]
    entries = [pool[index] for index in range(limit) for pool in social_pools if index < len(pool)]
    if not only_youtube:
        entries.extend(row for pool in pools[2:] for row in pool)
    return entries[:limit], list(dict.fromkeys(warnings))


def youtube_search(topic: str, limit: int, exclude_urls=()):
    """Independent public YouTube search; social results cannot consume its budget."""
    from . import main as m
    entries, seen, warnings = [], {m.canonical_url(url) for url in exclude_urls}, []
    # Read past previously used results before filtering; otherwise a new search
    # sees the same first page and runs out before reaching any unseen clips.
    pool_size = min(60, max(limit, limit + min(len(seen), 40)))
    for query in query_variants(topic)[:4]:
        if len(entries) >= limit:
            break
        try:
            raw = m.run([sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-cache-dir',
                     '--no-warnings', '--no-remote-components', '--flat-playlist', '--skip-download',
                     '--dump-single-json', '--socket-timeout', '10', '--retries', '0',
                     '--playlist-end', str(pool_size), '--', f'ytsearch{pool_size}:{query}'], 40)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError('Too many search results')
            for index, row in enumerate(json.loads(raw).get('entries', [])[:pool_size]):
                if not isinstance(row, dict) or not re.fullmatch(r'[\w-]{11}', str(row.get('id', ''))):
                    continue
                duration = row.get('duration')
                if (isinstance(duration, (int, float)) and not 2 <= duration <= m.MAX_SOURCE_SECONDS) or row.get('live_status') in ('is_live', 'is_upcoming'):
                    continue
                title = plain(row.get('title', ''))
                score = relevance(topic, title, plain(row.get('description', '')))
                if not score:
                    continue
                url = 'https://www.youtube.com/watch?v=' + row['id']
                identity = m.canonical_url(url)
                if identity in seen:
                    continue
                seen.add(identity)
                entries.append({'url': url, 'title': title[:100], 'source': 'YouTube', 'provider': 'youtube', 'search_score': score*.85 + .15/(index+1)})
        except Exception as error:
            warnings.append(search_warning('YouTube', 'YouTube', error))
            break
    if len(entries) < limit:
        options = {'exclude_urls': list(seen)} if exclude_urls else {}
        extra, engine_warnings = public_search(topic, True, limit, only_youtube=True, **options)
        warnings.extend(engine_warnings)
        for row in extra:
            identity = m.canonical_url(row['url'])
            if identity not in seen:
                seen.add(identity)
                entries.append(row)
    return entries[:limit], list(dict.fromkeys(warnings))


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


def select_free(candidates, topic, *, require_five=True):
    from . import main as m
    selected = []
    for candidate in candidates:
        path = m.DATA / 'media' / candidate['id'] / 'source'
        best_by_shot = {}
        try:
            windows = m.scene_windows(path)
            for window in windows:
                scene_start, scene_duration = window
                shot = getattr(window, 'shot', 0)
                duration = scene_duration
                start = scene_start
                raw = m.ffmpeg('-ss', str(start), '-i', str(path), '-t', str(duration), '-an',
                               '-vf', 'fps=3,scale=64:64,format=gray', '-f', 'rawvideo', 'pipe:1')
                score = window_score(raw)
                best = best_by_shot.get(shot)
                if score is not None and (best is None or score > best[0]):
                    best_by_shot[shot] = (score, start, duration, window)
            compilation = len({getattr(window, 'shot', 0) for window in windows}) > 1
            for technical, start, duration, window in best_by_shot.values():
                selected.append((float(candidate.get('search_score', 0)) * .8 + technical * .2, candidate, start, duration, compilation, window))
        except Exception:
            continue
    # Prefer one scene per source; only fill the remaining slots with distinct
    # shots from compilations. Multiple windows of one continuous shot never count.
    ordered = sorted(selected, key=lambda row: (row[1].get('source') == 'YouTube', -row[0]))
    chosen, seen = [], set()
    for row in ordered:
        if row[1]['id'] not in seen and len(chosen) < 5:
            chosen.append(row)
            seen.add(row[1]['id'])
    for row in ordered:
        if len(chosen) == 5:
            break
        if row not in chosen:
            chosen.append(row)
    if require_five and len(chosen) < 5:
        raise ValueError(f'Pouze {len(chosen)} různých scén je použitelných. Zkuste jiné téma nebo nahrajte vlastní klipy či kompilaci.')
    result = []
    for _, candidate, start, duration, compilation, window in sorted(chosen, key=lambda row: row[0]):
        result.append({**candidate, 'title': candidate['name'][:60], 'voiceover': '', 'start': start, 'duration': duration,
                       'sourceDuration': candidate['duration'], '_cut_scene': compilation,
                       'scene_start': getattr(window,'scene_start',start), 'scene_end': getattr(window,'scene_end',start+duration),
                       'review_required': getattr(window,'scene_end',start+duration)-getattr(window,'scene_start',start)>m.MAX_CLIP_SECONDS,
                       'reason': 'Výběr podle shody tématu, ostrosti a pohybu. Samostatný úsek bez detekovaného střihu; obsah a pořadí zkontroluj.'})
    return m.materialize_scenes(result)
