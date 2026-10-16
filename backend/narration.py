"""Explicit Czech male speech providers; no silent voice substitutions."""
import os
import shutil
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / '.runtime/tools/espeak'
MODELS = Path(os.environ.get('PIPER_MODEL_DIR', str(ROOT / '.runtime/models')))


def local_command():
    binary = shutil.which('espeak-ng')
    if binary:
        return [binary], os.environ.copy()
    binary = TOOLS / 'usr/bin/espeak-ng'
    if not binary.is_file():
        return None, None
    libraries = next((TOOLS / 'usr/lib').glob('*-linux-gnu'))
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(libraries) + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    return [str(binary), '--path=' + str(libraries)], env


def capabilities():
    command, _ = local_command()
    return {'local': bool(command), 'piper': all((MODELS / ('cs_CZ-jirka-medium' + suffix)).is_file() for suffix in ['.onnx', '.onnx.json']), 'blender': bool(shutil.which('blender'))}


def synthesize(text: str, provider: str, output: Path):
    if not text.strip():
        raise ValueError('Napiš text, který má vypravěč přečíst.')
    if provider == 'local':
        command, env = local_command()
        if not command:
            raise ValueError('Základní český hlas není nainstalovaný. Spusť scripts/install_speech.sh.')
        result = subprocess.run([*command, '-v', 'cs+m3', '-s', '145', '-p', '40', '-w', str(output), '--stdin'], input=text.encode(), capture_output=True, env=env, timeout=30)
        if result.returncode:
            raise RuntimeError('Lokální hlas se nepodařilo vytvořit: ' + result.stderr.decode(errors='replace')[-500:])
    elif provider == 'piper':
        if not capabilities()['piper']:
            raise ValueError('Hlas Jirka není stažený. Nejdřív povol Hugging Face a spusť scripts/download_models.py --language cs.')
        from piper import PiperVoice
        voice = PiperVoice.load(str(MODELS / 'cs_CZ-jirka-medium.onnx'))
        with wave.open(str(output), 'wb') as audio:
            voice.synthesize_wav(text, audio)
    else:
        raise ValueError('Neznámý hlas.')
    with wave.open(str(output), 'rb') as audio:
        duration = audio.getnframes() / audio.getframerate()
        if duration <= 0:
            raise ValueError('Hlas neobsahuje zvuk.')
    return duration
