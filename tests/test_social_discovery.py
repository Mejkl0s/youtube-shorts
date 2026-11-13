"""Public index fixtures; no claims about live network/model availability."""
import threading

import httpx
import pytest

from backend import free_search as f, main as m, work_budget as work


def row(source,identity):
    path={'TikTok':f'https://www.tiktok.com/@kids/video/{900000+identity}',
          'Instagram':f'https://www.instagram.com/reel/KID{identity}/',
          'YouTube':f'https://www.youtube.com/shorts/KIDFAIL{identity:04d}'}
    return {'url':path[source],'title':'Kids fails'}


def test_each_network_gets_concurrent_first_turn_with_job_context(monkeypatch):
    gate=threading.Barrier(3);budget=work.Budget(10);seen=[]
    def engine(query,provider,**kwargs):
        assert work.current() is budget
        source='TikTok' if 'tiktok.com' in query else 'Instagram' if 'instagram.com' in query else 'YouTube'
        seen.append(source);gate.wait(timeout=3)
        return [row(source,i) for i in range(4)]
    monkeypatch.setattr(f,'engine_results',engine)
    token=work._active.set(budget)
    try:results,_=f.public_search('kids fails',True,4,balanced=True)
    finally:work._active.reset(token)
    assert sorted(seen)==['Instagram','TikTok','YouTube']
    assert {item['source'] for item in results}=={'TikTok','Instagram','YouTube'}


def test_empty_or_bad_tiktok_query_does_not_disable_instagram_or_new_queries(monkeypatch):
    def engine(query,provider,**kwargs):
        if 'tiktok.com' in query:
            if 'inurl:video' in query:raise ValueError('Malformed result document: private-token')
            return [row('TikTok',1)]
        return [row('Instagram',2)]
    monkeypatch.setattr(f,'engine_results',engine)
    results,warnings=f.public_search('kids fails',False,8)
    assert {r['source'] for r in results}=={'TikTok','Instagram'}
    assert 'private-token' not in str(warnings)


def test_pages_read_past_previous_results_and_empty_network_does_not_cap_pool(monkeypatch):
    seen=[]
    def engine(query,provider,*,page=0,**kwargs):
        seen.append((query,page))
        if 'instagram.com' in query:return []
        return [row('TikTok',i+page*20) for i in range(20)]
    monkeypatch.setattr(f,'engine_results',engine)
    used=[row('TikTok',i)['url'] for i in range(20)]
    results,_=f.public_search('kids fails',False,24,exclude_urls=used,balanced=True)
    assert len(results)==24 and all(r['url'] not in used for r in results)
    assert any(page==2 for _,page in seen)


def test_instagram_alias_paths_are_searched_and_deduplicated(monkeypatch):
    seen=[]
    def engine(query,provider,**kwargs):
        seen.append(query)
        if 'instagram.com/reels/' in query:
            return [{'url':'https://www.instagram.com/reels/ABC/','title':'Children bloopers'}]
        if 'instagram.com/p/' in query:
            return [{'url':'https://www.instagram.com/p/ABC/?tracking=1','title':'Children bloopers'},
                    {'url':'https://www.instagram.com/p/DEF/','title':'Toddler funny mishap'}]
        return []
    monkeypatch.setattr(f,'engine_results',engine)
    results,_=f.public_search('funniest kid fails',False,8)
    assert len(results)==2
    assert len({m.canonical_url(r['url']) for r in results})==2
    assert any('instagram.com/p/' in query for query in seen)


@pytest.mark.parametrize('provider,param,value',[('bing','first','41'),('duckduckgo','s','60')])
def test_public_pagination_uses_real_provider_parameters(monkeypatch,provider,param,value):
    client=httpx.Client;seen=[]
    def response(request):
        seen.append(request)
        body=('<rss><channel><item><link>https://www.instagram.com/reel/ABC/</link>'
              '<title>Kids fails</title></item></channel></rss>' if provider=='bing' else
              '<a class="result__a" href="https://www.instagram.com/reel/ABC/">Kids fails</a>')
        return httpx.Response(200,text=body)
    monkeypatch.setattr(f.httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(response),**kw))
    assert len(f.engine_results('kids fails',provider,page=2))==1
    assert seen[0].url.params[param]==value


def test_kid_aliases_keep_subject_and_action_required():
    for title in ['Children bloopers','Toddler mishaps','#kidsfails','Baby tumbles']:
        assert f.relevance('funniest kid fails',title)>0,title
    for title in ['Children singing','Funny ski fails','Baby clothing sale']:
        assert f.relevance('funniest kid fails',title)==0,title


def test_nested_snippet_retains_the_whole_topic():
    parser=f.DuckResults()
    parser.feed('<a class="result__a" href="https://www.instagram.com/p/ABC/">Instagram</a>'
                '<div class="result__snippet">Funny <div>children</div> bloopers</div>')
    assert parser.results[0]['description']=='Funny children bloopers'
