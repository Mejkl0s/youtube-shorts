"""Choose whole moments inside a ceiling, never stretch to a target length."""
import math

MIN_CLIP_SECONDS = 1
MAX_PROJECT_SECONDS = 40
FPS = 30


def choose_moments(items, *, duration, score, identity, source, count=5, partial=False, max_seconds=MAX_PROJECT_SECONDS, brevity=False):
    """Bounded 0/1 knapsack. A physical event is considered at most once.

    Duration rounds UP for planning; rendering rounds down to complete frames.
    Source diversity breaks close editorial choices without cutting any event.
    """
    if not MIN_CLIP_SECONDS*count<=max_seconds<=MAX_PROJECT_SECONDS:
        raise ValueError("Neplatný celkový limit videa.")
    unique={}
    for item in items:
        key=identity(item)
        if key not in unique or score(item)>score(unique[key]):
            unique[key]=item
    rows=list(unique.values())
    # Bound work for long compilations while retaining short alternatives.
    if len(rows)>80:
        best=sorted(rows,key=score,reverse=True)[:40]
        shortest=sorted(rows,key=duration)[:40]
        rows=list({identity(row):row for row in best+shortest}.values())
    states={(0,0):(0.,(),frozenset(),0.)}
    limit=max_seconds*FPS
    for index,item in enumerate(rows):
        frames=math.ceil(duration(item)*FPS-1e-7)
        if not MIN_CLIP_SECONDS*FPS<=frames<=limit:
            continue
        for (n,used),(value,indices,sources,seconds) in list(states.items()):
            next_seconds=seconds+duration(item)
            # Per-item ceiling may add up to one frame each; validate the
            # exact sum too, rather than rejecting a valid 39.99-second set.
            if n==count or used+frames>limit+count or next_seconds>max_seconds+1e-7:
                continue
            next_sources=sources|{source(item)}
            next_value=value+float(score(item))+(2 if source(item) not in sources else 0)
            if brevity:next_value-=.025*float(duration(item))
            key=n+1,used+frames
            if key not in states or next_value>states[key][0]:
                states[key]=(next_value,indices+(index,),next_sources,next_seconds)
    feasible=[(key,state) for key,state in states.items() if key[0]==count or partial and key[0]>0]
    if not feasible:
        return []
    _,(_,indices,_,_)=max(feasible,key=lambda pair:(pair[0][0],pair[1][0],-pair[1][3]))
    return [rows[index] for index in indices]
