"""Local readiness check; no social downloads or paid provider calls."""
from pathlib import Path
import shutil
import tempfile
import sys

from backend import main as m
from backend.style import FONTS, filter_path


def main():
    for tool in ('node', 'npm', 'ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            raise RuntimeError('Chybi nastroj '+tool)
    for font in FONTS.values():
        if not Path(font).is_file():
            raise RuntimeError('Chybi pribalene pismo.')
    transport = m.run([sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-cache-dir', '--list-impersonate-targets'], 20)
    if b'curl_cffi' not in transport:
        raise RuntimeError('Stahovac nema doporucenou podporu curl_cffi. Spust instalaci ze SPUSTIT-WINDOWS.bat nebo aktualizuj zavislosti podle WINDOWS.md.')
    print('OK: stahovac rozpoznal podporu curl_cffi pro kompatibilni nacitani stranek.')
    with tempfile.TemporaryDirectory(prefix='Rank Studio ') as directory:
        folder = Path(directory)/"O'Brien [PC], ž; test"
        folder.mkdir()
        caption = folder/'caption.txt'
        caption.write_text('TOP 5 ZIMNÍCH PÁDŮ', encoding='utf-8')
        output = folder/'selftest.mp4'
        video_filter = f'drawtext=fontfile={filter_path(FONTS["bold"])}:textfile={filter_path(caption)}:fontsize=18:fontcolor=white:x=5:y=20'
        m.ffmpeg('-f', 'lavfi', '-i', 'color=c=blue:s=180x320:r=15:d=1',
                 '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-vf', video_filter,
                 '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(output))
        streams = m.probe(output)['streams']
        if not any(stream.get('codec_name') == 'h264' for stream in streams) or not any(stream.get('codec_name') == 'aac' for stream in streams):
            raise RuntimeError('Test kodovani H264/AAC selhal.')
    print('OK: skutecne MP4, H264/AAC, titulky, diakritika a cesty se specialnimi znaky.')
    health = m.health()
    print('Rozpoznani predlohy: '+('dostupne' if health['template_ocr'] else 'Tesseract chybi; pouzij rucni nastaveni vzhledu.'))
    print('Hlas bez API klice: '+('klient je nainstalovany; online hlas over tlacitkem prehrani.' if health['free_voice'] else 'klient chybi.'))
    print('Pristup k TikToku, Instagramu a YouTube tento offline test nepotvrzuje.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as error:
        print('CHYBA: '+str(error))
        raise SystemExit(1)
