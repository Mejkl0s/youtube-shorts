"""Prepare real local video analysis for the browser test; no external download."""
import json
import shutil
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import story
from backend.main import ffmpeg
from backend.story_reference import ReferenceRequest, prepare_reference

job_id=uuid.uuid4().hex
sources=ROOT/'.runtime/reference-fixtures'
sources.mkdir(exist_ok=True)
source=sources/f'{job_id}.mp4'
ffmpeg('-f','lavfi','-i','color=c=0xE63E24:size=240x360:rate=12:duration=2','-f','lavfi','-i','color=c=0x2858E6:size=240x360:rate=12:duration=2','-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]','-map','[v]','-c:v','libx264',str(source))
(story.DATA/job_id).mkdir()
story.jobs[job_id]={'id':job_id,'status':'queued','kind':'reference'}
def fixture_download(args,folder,timeout):
    assert 'yt_dlp' in args and args[-1]=='https://youtu.be/abcdefghijk'
    shutil.copyfile(source,folder/'reference.mp4')
try:
    with patch.object(story,'command',fixture_download):
        prepare_reference(job_id,ReferenceRequest(url='https://youtu.be/abcdefghijk'))
    assert story.jobs[job_id]['status']=='done',story.jobs[job_id]
    (ROOT/'.runtime/reference-check-id').write_text(job_id)
    print('Prepared actual local reference frames for browser validation; external downloading is replaced by a fixture.')
finally:
    source.unlink(missing_ok=True)
