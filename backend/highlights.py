"""Broad retrieval and per-video editorial review, followed by actual-cut audits."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import math

from . import work_budget as work, visual_selection as visual
from .timeline import choose_moments
from .event_signals import scan

RULES = visual.RULES.replace('40 seconds', '25 seconds')


def balanced(rows, limit):
    from . import main as m
    pools={name:[] for name in ('TikTok','Instagram','YouTube')};seen=set()
    for row in rows:
        key=m.canonical_url(row['url'])
        if key in seen:continue
        seen.add(key);pools[m.source_name(row['url'])].append(row)
    return [pool[i] for i in range(max((len(p) for p in pools.values()),default=0))
            for pool in pools.values() if i<len(pool)][:limit]


def search(body):
    from . import main as m
    warnings=[];rows=[]
    # Each worker receives the job's cancellation/deadline and provider snapshot.
    with ThreadPoolExecutor(max_workers=2,thread_name_prefix='highlight-search') as pool:
        tasks=[pool.submit(copy_context().run,m.public_search,body.topic,body.allow_youtube,
                           body.candidate_count,False,body.exclude_urls,balanced=True,seconds=75)]
        if body.allow_youtube:
            tasks.append(pool.submit(copy_context().run,m.youtube_search,body.topic,
                                     body.candidate_count,body.exclude_urls,fallback=False))
        for index,task in enumerate(tasks):
            try:
                found,notes=task.result()
                # Native YouTube results get their own place in the balanced
                # pool even if the public index already returned many URLs.
                if index:rows[0:0]=found
                else:rows.extend(found)
                warnings.extend(notes)
            except work.WorkStopped:raise
            except Exception:warnings.append('Jeden vyhledávací zdroj neodpověděl. Ostatní zdroje zůstaly v hledání.')
    return balanced(rows,body.candidate_count),list(dict.fromkeys(warnings))


def samples(path, start, end, action=None):
    result=visual.frames(path,start,end,min(25,max(5,math.ceil((end-start)*2)+1)))
    if action is not None:
        a=max(start,min(end-1,action-.65));b=min(end,max(a+1,action+.85))
        result+=visual.frames(path,a,b,min(22,math.ceil((b-a)*8)+1))
    return sorted({round(at,3):(at,image) for at,image in result}.values(),key=lambda row:row[0])


def review_video(candidate, topic, language, criteria):
    from . import main as m
    path=m.DATA/'media'/candidate['id']/'source';duration=candidate['duration']
    windows=m.scene_windows(path,full=True)
    signals=scan(path,duration)
    # Cover the complete source chronologically, then add evidence around
    # several different activity peaks. No peak is accepted without AI review.
    overview=visual.frames(path,0,duration,16)
    for signal in sorted(signals,key=lambda row:row['score'],reverse=True)[:3]:
        a=max(0,min(duration-1,signal['time']-.5));b=min(duration,a+1.5)
        overview+=visual.frames(path,a,b,5)
    overview=sorted({at:(at,image) for at,image in overview}.values(),key=lambda row:row[0])
    # Bound prompt size even for hundreds of physical shots. Only nominate
    # shots actually represented in the chronological overview/peak samples.
    visible_windows=[window for window in windows
                     if any(window.scene_start<=at<window.scene_end for at,_ in overview)]
    scene_bounds=[(window.scene_start,window.scene_end) for window in visible_windows]
    evidence=[{'type':'text','text':f'Topic: {topic!r}. Criteria: {criteria!r}. Source duration {duration:.3f}s. '
               f'Physical shot bounds: {scene_bounds}. Motion/color hints (NOT proof of an event): {signals}.'}]
    evidence+=visual.sheets(0,overview)
    scout=visual.request(RULES+' PER-VIDEO SCOUT: inspect this source across its timeline. '
        'Nominate its ONE strongest clearly visible complete incident, or none. Do not confuse a camera shake, '
        'flash, edit or color change with the main event. A short natural cut should usually take 2–5 seconds; '
        'at most 8 seconds, preserving enough setup and the visible outcome. Do not retain idle waiting. '
        'Start/end must stay in one stated physical shot. Return JSON '
        '{"shortlist":[{"start":1.0,"end":5.5,"action":3.0}]}, or {"shortlist":[]}.',evidence,650)
    proposals=scout.get('shortlist')
    if not isinstance(proposals,list) or len(proposals)>1:raise visual.VisualSelectionError('Neplatný návrh hlavního momentu.')
    if not proposals:return []
    item=proposals[0]
    if not isinstance(item,dict):raise visual.VisualSelectionError('Neplatný návrh hlavního momentu.')
    a,b,action=(visual.number(item.get(k)) for k in ('start','end','action'))
    shot=next((w for w in visible_windows if w.scene_start<=a<action<b<=w.scene_end),None)
    if shot is None or not 1<=b-a<=8:raise visual.VisualSelectionError('Návrh překračuje hranici záběru nebo délku momentu.')
    lower=max(shot.scene_start,a-1);upper=min(shot.scene_end,b+1)
    detailed=samples(path,lower,upper,action)
    scene={'candidate':candidate,'shot':shot.shot,'a':shot.scene_start,'b':shot.scene_end,'path':path}
    context=[{'type':'text','text':f'Scene 0. Source {candidate["id"]}. Evidence covers '
              f'{detailed[0][0]:.3f}–{detailed[-1][0]:.3f}s. Topic: {topic!r}. Criteria: {criteria!r}. '
              f'Language: {"Czech" if language=="cs" else "English"}.'}]+visual.sheets(0,detailed)
    reviewed=visual.request(RULES+' PER-VIDEO FINAL REVIEW: evaluate this incident on its own. '
        'Return {"moments":[]} if irrelevant, incomplete or unclear. Otherwise return at most ONE moment '
        'using scene=0, topic_match, complete, confidence, score (0–100), start, end, '
        'setup/action/outcome={time,observation}, title, voiceover, rank_note, reason. '
        'All evidence times are absolute source seconds. Include the full payoff and a short aftermath; '
        'prefer 2–5 seconds and reject any event needing more than 8 seconds. '
        'Use a concrete short title, 2–4 word voiceover and 2–4 word rank_note. '
        'Score uses an absolute clarity/action scale; reject events scoring below 60/100. No invented sound or unseen action. JSON only.',context,1500)
    accepted=visual.parse_review(reviewed,[scene],{0:(detailed[0][0],detailed[-1][0])})
    return [(score,clip) for score,clip in accepted if clip['duration']<=8 and score>=60]


def audit(clip, topic):
    from . import main as m
    path=m.DATA/'media'/clip['id']/'source'
    # These frames come from the already materialized cut, not the full source.
    action=clip['visual_review']['action']['time']-clip['source_start']
    evidence=[{'type':'text','text':f'Topic: {topic!r}. This is the actual exported excerpt, '
               f'{clip["duration"]:.3f}s long. Its timestamps are LOCAL to this cut.'}]
    evidence+=visual.sheets(0,samples(path,0,clip['duration'],action))
    result=visual.request(RULES+' CUT AUDIT: check this finished cut independently. '
        'Does it clearly show enough preparation, the main action and its visible completed outcome? '
        'Reject cut-off endings, confusing beginnings, irrelevant clips or merely camera/color changes. '
        'Return JSON {"accepted":true,"topic_match":true,"complete":true,"action_visible":true,'
        '"outcome_visible":true,"confidence":0.9,"reason":"specific visible evidence"}. '
        'Use false when uncertain. This is a visual check, not a guarantee.',evidence,600)
    return (all(result.get(k) is True for k in ('accepted','topic_match','complete','action_visible','outcome_visible'))
            and .8<=visual.number(result.get('confidence',0))<=1 and isinstance(result.get('reason'),str)
            and bool(result['reason'].strip()))


def compare_cuts(clips, topic):
    """Catch re-encoded/cross-platform reposts after individual event reviews."""
    from . import main as m
    evidence=[{'type':'text','text':f'Topic: {topic!r}. Compare these actual cut images. '
               'Identical incidents may have different crops, watermarks or encodings.'}]
    for index,clip in enumerate(clips):
        evidence.extend(visual.sheets(index,visual.frames(m.DATA/'media'/clip['id']/'source',0,clip['duration'],5)))
    result=visual.request(RULES+' SET AUDIT: identify repeated incidents across the given cuts. '
        'Return JSON {"distinct":true,"duplicates":[],"confidence":0.9,"reason":"visible differences"}. '
        'For repeats set distinct=false and duplicates=[{"duplicate":1,"original":0}]. '
        'Use scene indices, never source titles as evidence. Each repeated incident needs one retained original. '
        'Same topic, objects or background alone do not prove a duplicate. Lower confidence if uncertain.',evidence,800)
    pairs=result.get('duplicates')
    if (not isinstance(pairs,list) or len(pairs)>=len(clips)
            or not .8<=visual.number(result.get('confidence',0))<=1
            or not isinstance(result.get('reason'),str) or not result['reason'].strip()
            or result.get('distinct') is not (not bool(pairs))):
        raise visual.VisualSelectionError('AI nedokázala spolehlivě porovnat rozdílnost momentů.')
    rejected=set();originals=set()
    for pair in pairs:
        if not isinstance(pair,dict):raise visual.VisualSelectionError('Neplatné porovnání momentů.')
        a,b=pair.get('duplicate'),pair.get('original')
        if type(a) is not int or type(b) is not int or not 0<=a<len(clips) or not 0<=b<len(clips) or a==b or a in rejected:
            raise visual.VisualSelectionError('Neplatné indexy opakovaných momentů.')
        rejected.add(a);originals.add(b)
    if rejected & originals:raise visual.VisualSelectionError('Opakovaný moment nemá zachovaný originál.')
    return rejected


def select(candidates,body, report):
    from . import main as m
    token=visual._provider.set('local' if body.mode=='local' else 'openai')
    accepted=[];audited={};rejected=set();compared=set()
    try:
        for i,candidate in enumerate(candidates):
            work.stage(f'Prohlížím celé video {i+1}/{len(candidates)} a hledám jeho hlavní moment…')
            try:rows=review_video(candidate,body.topic,body.language,body.ranking_criteria)
            except visual.VisualSelectionError:rows=[]
            accepted.extend(rows);report(candidate,bool(rows))
        while True:
            work.checkpoint()
            options=[row for row in accepted if row[1]['id'] not in rejected]
            chosen=choose_moments(options,duration=lambda row:row[1]['duration'],score=lambda row:row[0]/100,
                identity=lambda row:row[1]['id'],source=lambda row:row[1]['id'],partial=True,
                max_seconds=body.max_duration,brevity=True)
            pending=[row for row in chosen if row[1]['id'] not in audited]
            if not pending:
                signature=tuple(row[1]['id'] for row in chosen)
                if len(chosen)>1 and signature not in compared:
                    work.stage('Porovnávám hotové momenty a ověřuji, zda nejde o opakované události…')
                    try:duplicates=compare_cuts([audited[row[1]['id']] for row in chosen],body.topic)
                    except visual.VisualSelectionError:
                        # Preserve the audited work without presenting an
                        # unverified full set as a successful ranking.
                        best=sorted(chosen,key=lambda row:row[0],reverse=True)[:4]
                        partial=[audited[row[1]['id']] for row in reversed(best)]
                        if work.current():work.current().visual_clips=partial
                        return partial
                    compared.add(signature)
                    if duplicates:
                        rejected.update(chosen[index][1]['id'] for index in duplicates)
                        continue
                break
            for _,original in pending:
                work.stage(f'Kontroluji hotový výřez: {len(audited)+1} prověřených momentů…')
                cut=m.materialize_scenes([original])[0]
                try:valid=audit(cut,body.topic)
                except visual.VisualSelectionError:valid=False
                if valid:
                    cut['visual_review']['cut_audit']={'accepted':True,'method':'actual-cut-frames'}
                    cut['visual_review']['method']='adaptive-event-v3'
                    from .desktop_secrets import atomic_json
                    meta=m.asset(cut['id']);meta['visual_review']=cut['visual_review']
                    atomic_json(m.DATA/'media'/cut['id']/'metadata.json',meta)
                    audited[original['id']]=cut
                else:rejected.add(original['id'])
            if work.current():work.current().visual_clips=[audited[row[1]['id']] for row in chosen if row[1]['id'] in audited]
        result=[audited[row[1]['id']] for row in sorted(chosen,key=lambda row:row[0]) if row[1]['id'] in audited]
        if work.current():work.current().visual_clips=result
        return result
    finally:visual._provider.reset(token)


def discover(job_id, body):
    from . import main as m
    candidates=[];warnings=[];failures=[];stats={name:{'found':0,'downloaded':0,'failed':0,'reviewed':0,'accepted':0}
                                   for name in ('TikTok','Instagram','YouTube')}
    def publish(**changes):m.set_job(job_id,source_stats={k:dict(v) for k,v in stats.items()},warnings=list(dict.fromkeys(warnings)),
                                    downloaded_sources=list(candidates),download_failures=list(failures),candidate_count=len(candidates),max_duration=body.max_duration,**changes)
    try:
        work.stage('Hledám širší výběr na TikToku, Instagramu i přímo na YouTube…')
        publish(status='searching',progress=3)
        entries,warnings=search(body)
        for row in entries:stats[m.source_name(row['url'])]['found']+=1
        publish(progress=10,search_results=[{'url':row['url'],'title':row['title']} for row in entries],youtube_fallback=False)
        excluded=set()
        for identity in body.exclude_asset_ids:
            try:excluded.add(m.original_hash(identity))
            except (OSError,ValueError,m.HTTPException):pass
        blocked={}
        for i,row in enumerate(entries):
            work.checkpoint()
            if len(candidates)>=24:break
            source=m.source_name(row['url'])
            if blocked.get(source,0)>=2:continue
            work.stage(f'Načítám {source}: {len(candidates)}/24 videí připraveno k posouzení…')
            try:video=m.download_candidate({**row,'source':source,'_excluded_content':excluded})
            except work.WorkStopped:raise
            except Exception as error:
                kind,reason=m.download_failure(error);stats[source]['failed']+=1
                if kind in ('blocked','timeout','login_required'):blocked[source]=blocked.get(source,0)+1
                failures.append({'source':source,'url':row['url'],'kind':kind,'reason':reason})
                warnings.append(f'{source}: {reason}')
                if blocked.get(source)==2:
                    warnings.append(f'{source}: po dvou omezeních zdroje je další stahování v tomto hledání pozastavené; pokračuji ostatními sítěmi.')
            else:
                if video.get('content_sha256'):excluded.add(video['content_sha256'])
                candidates.append(video);stats[source]['downloaded']+=1
            publish(progress=10+int(30*(i+1)/max(1,len(entries))))
        def reviewed(candidate,ok):
            row=stats.get(candidate.get('source') or m.source_name(candidate.get('source_url','')),stats['YouTube'])
            row['reviewed']+=1;row['accepted']+=int(ok)
            publish(progress=40+int(40*sum(s['reviewed'] for s in stats.values())/max(1,len(candidates))))
        clips=select(candidates,body,reviewed) if candidates else []
        m.assign_notes(clips,body.language,body.exclude_notes)
        if body.blur_text:m.add_cleanup(clips,warnings)
        if len(clips)==5:
            publish(status='done',progress=100,clips=clips,message='Pět krátkých momentů prošlo obsahovým posouzením i kontrolou výřezů. Přehraj je před zveřejněním.')
        else:
            publish(status='failed',progress=100,partial_clips=clips,message=f'Přísnou kontrolou prošlo {len(clips)}/5 momentů v limitu {body.max_duration:g} s. Nejasné nebo nedokončené události nebyly doplněny náhodnými klipy.')
    except work.WorkStopped:
        publish(partial_clips=getattr(work.current(),'visual_clips',[]))
        raise
    except Exception:
        publish(status='failed',progress=100,partial_clips=getattr(work.current(),'visual_clips',[]),
                message='Důkladný výběr se zastavil při načítání nebo posouzení. Ověř vybraný vizuální model a připojení; dokončené zdroje zůstaly zachované.')
