"""Cheap full-source RGB/motion scan; signals nominate times, not semantic facts."""
import numpy as np
from . import work_budget as work


def scan(path, duration):
    from . import main as m
    raw=m.ffmpeg('-i',str(path),'-t',str(min(duration,600)),'-an','-vf',
                 'fps=3,scale=96:54,format=rgb24','-f','rawvideo','pipe:1',timeout=100)
    size=96*54*3
    if len(raw)%size or len(raw)<size*2:return []
    images=np.frombuffer(raw,np.uint8).reshape(-1,54,96,3)
    values=[];previous_hist=None;previous=None
    for i,image in enumerate(images):
        work.checkpoint()
        small=image[::2,::2].astype(np.float32).mean(axis=2)
        bins=(image//32).astype(np.int32)
        hist=np.bincount((bins[:,:,0]*64+bins[:,:,1]*8+bins[:,:,2]).ravel(),minlength=512).astype(float)
        hist/=hist.sum()
        if previous is not None:
            # Compensate a small global camera translation before looking for
            # localized residual action. Uniform shake alone is a weak signal.
            residuals=[np.abs(previous-np.roll(small,(dy,dx),(0,1)))
                       for dy in (-2,0,2) for dx in (-2,0,2)]
            # Fit on the interior, but retain edge evidence: an incident at
            # the image edge must not disappear from the activity score.
            residual=min(residuals,key=lambda value:float(value[2:-2,2:-2].mean()))
            local=float(np.percentile(residual,98)-np.median(residual))/64
            change=float(np.abs(hist-previous_hist).sum())/2
            values.append({'time':round(i/3,3),'motion':min(1,max(0,local)),
                           'color':round(change,4),'score':min(1,max(0,local))*.75+min(change,.5)*.25})
        previous,previous_hist=small,hist
    chosen=[]
    for row in sorted(values,key=lambda value:value['score'],reverse=True):
        if row['score']<.025:break
        if all(abs(row['time']-old['time'])>2 for old in chosen):chosen.append(row)
        if len(chosen)==6:break
    return sorted(chosen,key=lambda row:row['time'])
