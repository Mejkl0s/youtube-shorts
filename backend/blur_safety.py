"""Shared spatial budgets for unobtrusive text cleanup, including saved masks."""
MAX_AUTO_AREA = .085


def narrow(region):
    r=region.model_dump() if hasattr(region,'model_dump') else region
    return (r['w']<=.9 and r['h']<=.075 and r['w']*r['h']<=.04
            and r.get('kind')!='block')


def safe_regions(regions):
    result=[];area=0
    for region in regions:
        r=region.model_dump() if hasattr(region,'model_dump') else region
        explicit=r.get('origin','manual')=='manual' and r.get('allow_large') is True
        size=r['w']*r['h']
        if not explicit and (not narrow(r) or area+size>MAX_AUTO_AREA+1e-8):continue
        result.append(region)
        if not explicit:area+=size
    return result
