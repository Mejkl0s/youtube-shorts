import uuid
import numpy as np
import pytest
from backend import main as m
from backend.audio_tail import ending_spike, tail_filter
from test_workflow import isolated


def tone(amplitude, seconds, rate=8000):
    return amplitude*np.sin(2*np.pi*440*np.arange(round(seconds*rate))/rate)


def test_only_abrupt_loud_tail_is_softened():
    sudden=np.concatenate([tone(.03,1.2),tone(.9,.3)])
    onset,gain=ending_spike(sudden,8000,4)
    assert 3.65<onset<3.75 and .04<=gain<.1
    assert ending_spike(tone(.9,1.5),8000,4) is None
    assert ending_spike(tone(.03,1.5),8000,4) is None
    assert ending_spike(np.concatenate([tone(.9,1),tone(.03,.5)]),8000,4) is None


@pytest.mark.parametrize('mode',['auto','keep','mute'])
def test_real_filtered_audio_preserves_event_and_duration(isolated,mode):
    source=isolated/'ending.wav'
    m.ffmpeg('-f','lavfi','-i',"aevalsrc=if(lt(t\\,3.7)\\,0.03\\,0.9)*sin(2*PI*440*t):s=8000:d=4",str(source))
    filters=tail_filter(source,0,4,mode)
    raw=m.ffmpeg('-i',str(source),'-af',filters+'anull','-ac','1','-ar','8000','-f','f32le','pipe:1')
    samples=np.frombuffer(raw,dtype='<f4')
    rms=lambda a:np.sqrt(np.mean(a*a))
    assert len(samples)==32000
    assert .019<rms(samples[8000:16000])<.023
    tail=rms(samples[-1600:-160])
    if mode=='keep':assert tail>.6
    elif mode=='mute':assert tail<.00001
    else:assert tail<.09


def test_real_export_applies_tail_modes_only_to_original_sound(isolated):
    clips=[]
    for mode in ['auto','keep','mute','keep','auto']:
        folder=isolated/'media'/uuid.uuid4().hex;folder.mkdir()
        m.ffmpeg('-f','lavfi','-i','color=c=blue:s=160x284:r=15:d=2','-f','lavfi','-i',
                 'aevalsrc=if(lt(t\\,1.7)\\,0.03\\,0.9)*sin(2*PI*440*t):s=44100:d=2',
                 '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-f','mp4',str(folder/'source'))
        meta=m.register(folder/'source',folder.name,'Tail fixture')
        clips.append({**meta,'title':'Tail fixture','voiceover':'','duration':2,'end_audio':mode})
    project=m.Project(title='TAIL TEST',clips=clips,voice=False,effects=False,original_volume=1,resolution='720')
    job=uuid.uuid4().hex;m.jobs[job]={'id':job};m.render(job,project)
    assert m.jobs[job]['status']=='done',m.jobs[job]
    path=isolated/'jobs'/job/'ranking.mp4'
    raw=m.ffmpeg('-i',str(path),'-vn','-ac','1','-ar','8000','-f','f32le','pipe:1')
    sound=np.frombuffer(raw,dtype='<f4')
    for index,mode in enumerate(['auto','keep','mute','keep','auto']):
        end=sound[round((index*2+1.8)*8000):round((index*2+1.95)*8000)]
        level=np.sqrt(np.mean(end*end))
        assert (level>.55 if mode=='keep' else level<.09),(mode,level)
    assert abs(float(m.probe(path)['format']['duration'])-10)<.08
