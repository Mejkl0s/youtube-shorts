"""Fit complete spoken lines into existing cuts without stretching the video."""
import math
import os
import wave

import numpy as np


MAX_SPEED = 1.25


def speech_bounds(samples, rate):
    """Trim boundary silence only; retain quiet consonants and internal pauses."""
    values = np.asarray(samples)
    if not len(values):
        raise ValueError('Hlasová služba vrátila prázdný zvuk. Zkus vytvořit hlas znovu.')
    size = max(1, round(rate*.01))
    padded = np.pad(values.astype(np.float64)/32768, (0, (-len(values)) % size))
    rms = np.sqrt(np.mean(padded.reshape(-1, size)**2, axis=1))
    threshold = max(.0005, float(rms.max())*.005)
    active = np.flatnonzero(rms > threshold)
    if not len(active):
        raise ValueError('Hlasová služba vrátila pouze ticho. Zkus vytvořit hlas znovu.')
    return max(0, active[0]*size-round(rate*.08)), min(len(values), (active[-1]+1)*size+round(rate*.1))


def trim_speech(path):
    from . import main as m
    rate = 24000
    seconds = float(m.probe(path)['format']['duration'])
    if not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise ValueError('Hlasová služba vrátila neplatnou délku zvuku.')
    raw = m.ffmpeg('-i', str(path), '-vn', '-ac', '1', '-ar', str(rate), '-f', 's16le', 'pipe:1')
    samples = np.frombuffer(raw, dtype='<i2')
    first, last = speech_bounds(samples, rate)
    temporary = path.with_suffix('.fit.wav')
    try:
        with wave.open(str(temporary), 'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
            out.writeframes(samples[first:last].tobytes())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return (last-first)/rate


def placement(speech_seconds, clip_seconds):
    """Prefer a short lead-in, reducing it before considering excessive speed."""
    tail = min(.12, clip_seconds*.06)
    preferred = .15 if clip_seconds < 2 else .4
    if speech_seconds > (clip_seconds-tail)*MAX_SPEED+1e-7:
        return None
    delay = min(preferred, max(0, clip_seconds-tail-speech_seconds))
    # Quantize before calculating speed so adelay never moves the last word out.
    delay_ms = math.floor(delay*1000)
    speed = max(1., speech_seconds/(clip_seconds-tail-delay_ms/1000))
    return min(MAX_SPEED, speed), delay_ms


def short_rank_line(rank, language):
    lines = ['První.', 'Druhé.', 'Třetí.', 'Čtvrté.', 'Páté.'] if language=='cs' else ['One.', 'Two.', 'Three.', 'Four.', 'Five.']
    return lines[rank-1]
