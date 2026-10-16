"""Explicit English male speech providers; no silent voice substitutions."""
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
    return {'local': bool(command), 'piper': all((MODELS / ('en_US-ryan-medium' + suffix)).is_file() for suffix in ['.onnx', '.onnx.json']), 'blender': bool(shutil.which('blender')), 'ai': bool(os.environ.get('OPENAI_API_KEY')), 'openai': bool(os.environ.get('OPENAI_API_KEY'))}


def synthesize(text: str, provider: str, output: Path):
    if not text.strip():
        raise ValueError('Enter the narration text.')
    if provider == 'local':
        command, env = local_command()
        if not command:
            raise ValueError('The basic English male voice is not installed. Run scripts/install_speech.sh.')
        result = subprocess.run([*command, '-v', 'en-us+m3', '-s', '150', '-p', '40', '-w', str(output), '--stdin'], input=text.encode(), capture_output=True, env=env, timeout=30)
        if result.returncode:
            raise RuntimeError('Local speech generation failed: ' + result.stderr.decode(errors='replace')[-500:])
    elif provider == 'piper':
        if not capabilities()['piper']:
            raise ValueError('Ryan is not installed. Allow the model download and run scripts/download_models.py --language en-male.')
        from piper import PiperVoice
        voice = PiperVoice.load(str(MODELS / 'en_US-ryan-medium.onnx'))
        with wave.open(str(output), 'wb') as audio:
            voice.synthesize_wav(text, audio)
    elif provider == 'openai':
        if not os.environ.get('OPENAI_API_KEY'):
            raise ValueError('OpenAI narration requires a configured API key.')
        from .main import synthesize as premium_speech
        from .style import VoiceSettings
        try:
            premium_speech(text, 'en', output, VoiceSettings(provider='openai', voice='onyx', speed=1, delivery='Speak natural, clear English in a warm male storytelling voice. Follow the punctuation. Keep sentence endings intact.'))
        except Exception as error:
            raise ValueError('The natural voice provider is unavailable. Check the API key, network access and provider credit.') from error
    else:
        raise ValueError('Unknown voice.')
    with wave.open(str(output), 'rb') as audio:
        duration = audio.getnframes() / audio.getframerate()
        if duration <= 0:
            raise ValueError('The generated voice contains no audio.')
    return duration
