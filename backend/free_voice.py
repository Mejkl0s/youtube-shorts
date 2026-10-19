"""Keyless online speech via edge-tts. Never fall back to a paid provider."""
import asyncio
from importlib.util import find_spec
import os
from pathlib import Path
import tempfile


MALE_VOICES = {'en': 'en-US-AndrewMultilingualNeural', 'cs': 'cs-CZ-AntoninNeural'}


def available():
    return find_spec('edge_tts') is not None


def synthesize(text: str, language: str, output: Path, speed: float):
    from . import main as m
    import edge_tts
    if language not in MALE_VOICES:
        raise ValueError('Bezplatný hlas podporuje angličtinu a češtinu.')
    proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    rate = f'{round((speed-1)*100):+d}%'
    async def generate(path):
        speech = edge_tts.Communicate(text, voice=MALE_VOICES[language], rate=rate,
                                     proxy=proxy, connect_timeout=10, receive_timeout=20)
        await asyncio.wait_for(speech.save(str(path)), timeout=35)
    try:
        with tempfile.TemporaryDirectory(prefix='free-voice-', dir=output.parent) as directory:
            mp3 = Path(directory)/'speech.mp3'
            asyncio.run(generate(mp3))
            if not mp3.is_file() or mp3.stat().st_size < 100:
                raise ValueError('Empty audio')
            m.ffmpeg('-i', str(mp3), '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', str(output))
            metadata = m.probe(output)
            if not any(stream['codec_type'] == 'audio' for stream in metadata['streams']):
                raise ValueError('Invalid audio')
    except Exception:
        output.unlink(missing_ok=True)
        # Network errors can contain proxy URLs. Return neither credentials nor raw traces.
        raise ValueError('Bezplatný online hlas teď není dostupný. Služba mohla odmítnout server nebo neodpověděla. Zkus ukázku později, zvol jiný dostupný hlas nebo vypni voiceover. Na placený hlas se aplikace nepřepnula.') from None
