"""Sparse event-relative sound design. Visual evidence first, motion only as a hint."""
import math
import wave

import numpy as np


def _number(value):
    return type(value) in (int,float) and math.isfinite(value)


def visual_moment(clip, metadata):
    review=clip.visual_review or {}
    confidence=review.get('confidence',0)
    if not _number(confidence) or confidence<.8:return None
    offset=float(metadata.get('source_start',0))+clip.start
    events=[review.get(key,{}) for key in ('setup','action','outcome')]
    if not all(isinstance(e,dict) and _number(e.get('time')) and e.get('observation') for e in events):return None
    setup,action,outcome=(e['time']-offset for e in events)
    if 0<=setup<action<outcome<=clip.duration and .25<=action<=clip.duration-.25:
        return action,outcome
    return None


def motion_moment(path,start,duration):
    from . import main as m
    raw=m.ffmpeg('-ss',str(start),'-i',str(path),'-t',str(duration),'-an',
                 '-vf','fps=8,scale=96:96,format=gray','-f','rawvideo','pipe:1',timeout=40)
    values=np.frombuffer(raw,np.uint8)
    if values.size<96*96*6 or values.size%(96*96):return None
    frames=values.reshape(-1,96,96).astype(np.float32)
    delta=np.abs(np.diff(frames,axis=0))
    # Uniform flashes and changes over most of the frame are not local action.
    residual=np.maximum(0,delta-np.median(delta,axis=(1,2))[:,None,None])
    energy=residual.mean(axis=(1,2));coverage=(delta>24).mean(axis=(1,2))
    times=(np.arange(len(energy))+1)/8
    eligible=(times>=.45)&(times<=duration-.4)&(coverage<.6)
    if not eligible.any():return None
    index=int(np.argmax(np.where(eligible,energy,0)))
    baseline=float(np.median(energy[eligible]))
    if energy[index]<max(3.,baseline*3.5) or coverage[index]<.015:return None
    return float(times[index])


def source_levels(path,start,duration,has_audio):
    if not has_audio:return np.zeros(0)
    from . import main as m
    raw=m.ffmpeg('-ss',str(start),'-i',str(path),'-t',str(duration),'-vn','-ac','1','-ar','8000','-f','f32le','pipe:1',timeout=30)
    values=np.frombuffer(raw,dtype='<f4').astype(float);size=160
    return np.sqrt(np.mean(values[:len(values)//size*size].reshape(-1,size)**2,axis=1)) if len(values)>=size else np.zeros(0)


def plan_effects(clip,metadata,path,rank,original_gain=1.):
    result={'rank':rank,'source':'none','events':[],'reason':'Bez jasného momentu ponechán původní zvuk.'}
    if clip.effects_mode=='off':return {**result,'reason':'Efekty u tohoto klipu jsou vypnuté.'}
    trusted=visual_moment(clip,metadata)
    if clip.effects_mode=='manual':
        action=min(clip.duration-.12,max(.12,clip.effect_at));outcome=None;source='manual'
    elif trusted:action,outcome=trusted;source='visual'
    else:
        action=motion_moment(path,clip.start,clip.duration);outcome=None;source='motion'
        if action is None:return result
    levels=source_levels(path,clip.start,clip.duration,metadata.get('has_audio',False))*original_gain
    near=levels[max(0,int((action-.08)/.02)):int((action+.15)/.02)]
    loud=bool(len(near) and float(near.max())>.12)
    result.update(source=source,reason='Čas určen ručně.' if source=='manual' else 'Hlavní moment podle obrazového posouzení.' if source=='visual' else 'Jemný důraz podle výrazné lokální změny pohybu; děj zkontroluj.')
    events=[]
    def add(kind,at,gain):
        length={'whoosh':.18,'accent':.14,'chime':.24}[kind]
        lead=.18 if kind=='whoosh' else .02
        beginning=max(0,at-lead)
        if beginning+length<=clip.duration-.025:
            events.append({'kind':kind,'at':round(at,3),'start':round(beginning,4),'duration':length,'gain':gain})
    if source=='motion':
        if not loud:add('whoosh',action,.45)
    else:
        if not loud:add('accent',action,1.)
        if rank==1 and outcome is not None and outcome-action>=.8 and outcome<=clip.duration-.35 and not loud:
            add('chime',outcome,.55)
        elif action>=.65:add('whoosh',action,.45 if loud else .65)
    result['events']=sorted(events,key=lambda e:e['start'])[:2]
    if loud:result['reason']='Důležitý původní zvuk zůstává dominantní; další úder se nepřidává.'
    return result


def render_effects(path,duration,plan,rank,voice_window=None):
    rate=44100;mix=np.zeros(round(duration*rate),dtype=float)
    for index,event in enumerate(plan['events']):
        length=event['duration'];t=np.arange(round(length*rate))/rate
        if event['kind']=='whoosh':
            rng=np.random.default_rng(rank*41+index)
            noise=np.convolve(rng.normal(0,1,len(t)),np.ones(3)/3,mode='same')
            signal=(noise*.10+np.sin(2*np.pi*(700*t+2500*t*t))*.04)*np.sin(np.pi*t/length)**2
        elif event['kind']=='accent':
            envelope=np.minimum(1,t/.02)*np.exp(-np.maximum(0,t-.02)*32)
            signal=(np.sin(2*np.pi*(220*t-200*t*t))*.20+np.sin(2*np.pi*980*t)*.025)*envelope
        else:
            envelope=np.minimum(1,t/.015)*(1-t/length)**2
            signal=sum(np.sin(2*np.pi*f*t) for f in (659.25,783.99,987.77))*.04*envelope
        begin=round(event['start']*rate);n=min(len(signal),len(mix)-begin)
        if n<=0:continue
        gain=np.full(n,event['gain'],dtype=float)
        if voice_window:
            absolute=event['start']+np.arange(n)/rate;a,b=voice_window
            # Smooth ducking prevents SFX from competing with the spoken line.
            fade=np.minimum(np.clip((absolute-a+.04)/.04,0,1),np.clip((b+.04-absolute)/.04,0,1))
            gain*=1-.65*fade
        signal=signal[:n]*gain
        signal[:min(132,n)]*=np.linspace(0,1,min(132,n))
        signal[-min(220,n):]*=np.linspace(1,0,min(220,n))
        mix[begin:begin+n]+=signal
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
        out.writeframes((np.clip(mix,-.85,.85)*32767).astype('<i2').tobytes())
