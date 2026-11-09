"""Conservative, amplitude-based ending cleanup; never cuts video or speech tracks."""
import numpy as np


def ending_spike(samples, rate, duration):
    """Return onset/gain for a sudden sustained rise confined to the last 0.5s."""
    size = max(1, round(rate * .025))
    values = np.asarray(samples, dtype=np.float64)
    if len(values) < size * 24 or not np.isfinite(values).all():
        return None
    blocks = values[:len(values)//size*size].reshape(-1, size)
    rms = np.sqrt(np.mean(blocks*blocks, axis=1))
    # Context is decoded from at most the last 1.5 seconds of the selected cut.
    boundary = len(rms) - 20
    reference = max(.005, float(np.median(rms[:boundary])))
    threshold = max(.18, reference * 3.16)
    if float(np.median(rms[-4:])) < threshold:
        return None
    high = np.flatnonzero(rms >= threshold)
    if not len(high) or high[0] < boundary:
        return None  # The loud event was already underway: preserve its sound.
    onset = duration - len(values)/rate + high[0]*size/rate
    gain = min(.3, max(.04, reference*1.8 / float(np.max(rms[high]))))
    return max(0, onset-.025), gain


def tail_filter(source, start, duration, mode='auto'):
    if mode == 'keep':
        return ''
    if mode == 'mute':
        at = max(0, duration-.5)
        return f'afade=t=out:st={at:.6f}:d=0.04,'
    from . import main as m
    window = min(1.5, duration)
    raw = m.ffmpeg('-ss', str(start+duration-window), '-i', str(source), '-t', str(window),
                   '-vn', '-ac', '1', '-ar', '16000', '-f', 'f32le', 'pipe:1', timeout=30)
    spike = ending_spike(np.frombuffer(raw, dtype='<f4'), 16000, duration)
    ending = f'afade=t=out:st={max(0,duration-.012):.6f}:d=0.012,'
    if spike:
        onset, gain = spike
        ramp = f'min(1,max(0,(t-{onset:.6f})/0.04))'
        return f"volume='1-(1-{gain:.6f})*{ramp}':eval=frame," + ending
    return ending
