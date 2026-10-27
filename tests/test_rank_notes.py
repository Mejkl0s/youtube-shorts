import uuid

import numpy as np
import pytest
from pydantic import ValidationError

from backend import main as m
from backend.rank_notes import NOTE_BANK, fresh_notes, note_geometry
from test_workflow import isolated, make_source


def test_notes_are_short_independent_of_speech_and_follow_the_clip():
    clips=[m.Clip(id=f'{i:032x}',title='Long source title',voiceover='Number five.',duration=2) for i in range(5)]
    project=m.Project(title='Winter fails',clips=clips,voice=False)
    assert len({c.rank_note for c in project.clips})==5
    assert all(c.rank_note in NOTE_BANK['en'] for c in project.clips)
    project.clips[0].rank_note='Ice wins!'
    swapped=list(reversed(project.clips))
    restored=m.Project(title=project.title,clips=swapped,voice=False)
    assert restored.clips[-1].rank_note=='Ice wins!'
    assert restored.clips[-1].voiceover=='Number five.'
    assert m.Clip(id='a'*32,title='x',voiceover='',rank_note='').rank_note==''
    for text in ['A note with five whole words', 'x'*41, 'first\nsecond']:
        with pytest.raises(ValidationError):m.Clip(id='a'*32,title='x',voiceover='',rank_note=text)


def test_real_export_has_notes_at_numbers_without_legacy_middle_footer_or_active_box(isolated):
    clips=[]
    for i in range(5):
        meta=make_source(isolated/'media'/uuid.uuid4().hex,'purple',duration=2)
        clips.append({**meta,'title':'UNWANTED GREEN SOURCE TITLE','voiceover':'Unwanted bottom narration.','duration':2,
                      'rank_note':['Wait for it','Ice wins','Oops','No way','What a finale'][i]})
    layout=m.Layout(show_label=True,show_criteria=True,rank_color='00FF00',header_darkness=0)
    project=m.Project(title='WINTER FAILS',clips=clips,voice=False,effects=False,resolution='720',layout=layout)
    job=uuid.uuid4().hex
    m.jobs[job]={'id':job}
    m.render(job,project)
    assert m.jobs[job]['status']=='done',m.jobs[job]
    path=isolated/'jobs'/job/'ranking.mp4'
    frames=[]
    for at in (1,9):
        raw=m.ffmpeg('-ss',str(at),'-i',str(path),'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1')
        frames.append(np.frombuffer(raw,np.uint8).reshape(1280,720,3).astype(int))
    first,last=frames
    # Every static overlay is identical when the active rank changes: no gray box.
    assert np.abs(first-last).mean()<.5
    # Nothing from the studio is drawn over the bottom of the source anymore.
    assert np.abs(first[1000:-8]-[128,0,128]).max()<12
    green=(first[:,:,1]>180)&(first[:,:,0]<100)&(first[:,:,2]<100)
    assert green.sum()==0
    for marker in layout.rank_markers(5):
        text=project.clips[5-marker['rank']].rank_note
        x,y,size=note_geometry(text,m.FONTS[layout.font],marker,720,1280,layout.rank_x)
        assert x>720*layout.rank_x+20
        pixels=first[y:y+size+8,x:680]
        assert (pixels.min(axis=2)>185).sum()>20,marker

