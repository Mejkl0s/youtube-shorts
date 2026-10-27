"""Conservative temporal context and consistent portrait framing."""
import numpy as np

MAX_CLIP_SECONDS = 30


def portrait_filter(width, height, framing='fill'):
    if framing == 'fit':
        return f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1'
    return f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1'


def action_window(path, start, end):
    """Keep setup and aftermath around a motion peak; this is not semantic AI."""
    from . import main as m
    length=end-start
    if length <= MAX_CLIP_SECONDS:
        return start, length
    raw=m.ffmpeg('-ss',str(start),'-i',str(path),'-t',str(length),'-an',
                 '-vf','fps=2,scale=64:64,format=gray','-f','rawvideo','pipe:1',timeout=120)
    frames=np.frombuffer(raw,np.uint8)
    if frames.size < 8192 or frames.size % 4096:
        raise ValueError('Nedostatek snímků pro posouzení pohybu.')
    frames=frames.reshape(-1,64,64).astype(np.float32)
    motion=np.abs(np.diff(frames,axis=0)).mean(axis=(1,2))
    # A short burst, rather than just one noisy frame, anchors the context.
    smoothed=np.convolve(motion,np.ones(min(3,len(motion)))/min(3,len(motion)),mode='same')
    peak=(int(smoothed.argmax())+1)/2
    return max(start,min(end-MAX_CLIP_SECONDS,start+peak-18)),float(MAX_CLIP_SECONDS)


def reframe_regions(regions, source_width, source_height, old, new):
    if old==new:
        return [r.model_dump() if hasattr(r,'model_dump') else r for r in regions]
    def transform(mode):
        scale=(min if mode=='fit' else max)(9/source_width,16/source_height)
        return scale,(9-source_width*scale)/2,(16-source_height*scale)/2
    a,ax,ay=transform(old)
    b,bx,by=transform(new)
    result=[]
    for region in regions:
        r=region.model_dump() if hasattr(region,'model_dump') else region
        x=max(0,min(1,((r['x']*9-ax)/a*b+bx)/9))
        y=max(0,min(1,((r['y']*16-ay)/a*b+by)/16))
        right=max(0,min(1,(((r['x']+r['w'])*9-ax)/a*b+bx)/9))
        bottom=max(0,min(1,(((r['y']+r['h'])*16-ay)/a*b+by)/16))
        if right-x>=.01 and bottom-y>=.01:
            result.append({**r,'x':x,'y':y,'w':right-x,'h':bottom-y})
    return result
