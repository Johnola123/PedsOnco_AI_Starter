"""Cached-profile analytics, never claims sampled results are full-dataset QC."""
import json
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import Dataset, DatasetProfile
from .modality import modality_summary, category_totals

router = APIRouter(prefix='/api/analytics',tags=['Data inventory and comparisons'])

def entries(db: Session):
    rows=db.execute(select(Dataset,DatasetProfile).outerjoin(DatasetProfile,Dataset.id==DatasetProfile.dataset_id)).all()
    return [(d, json.loads(p.profile_json) if p else None) for d,p in rows]

def fields(profile):
    """Report missingness ONLY for previewed columns; never interpret absent preview columns as nulls."""
    result={}
    if not profile:return result
    for table in (profile.get('tables',[])+profile.get('sheets',[])):
        if table.get('role')=='reference': continue
        name=table.get('name','data')
        preview=table.get('preview') or []
        for i, f in enumerate(table.get('fields') or []):
            key=str(f.get('name','')).strip()
            if not key: continue
            # A sheet may contain hundreds of headers, but only 12 previewed columns.
            sampled=(bool(preview) and i<len(preview[0]) and len(preview)>1)
            present=[r[i] if i<len(r) else None for r in preview[1:]] if sampled else []
            missing=sum(v is None or str(v).strip()=='' for v in present)
            result[f'{name}.{key}']={'table':name,'field':key,'type':f.get('inferred_type'),
              'sample_observed':len(present),'sample_missing':missing if sampled else None,
              'sample_missing_pct':round(100*missing/len(present),1) if present else None,
              'sample_status':'preview' if present else 'not_sampled'}
    return result

def item(d,p):
    f=fields(p)
    return {'id':d.id,'cohort':d.project_name,'name':d.original_name,'size_bytes':d.size_bytes,
            'source_type':d.source.source_type if d.source else 'unknown','source_url':d.source.source_url if d.source else None,
            'format':p.get('format') if p else None,'profile_status':'cached' if p else 'not_profiled',
            'table_count':p.get('table_count',0) if p else None,'fields':list(f.values()),
            'modality':modality_summary(p,d.original_name), 'field_count':len(f),'field_names':sorted(set(x['field'] for x in f.values())),
            'warning':'Missingness uses cached preview sample only, not all rows.' if p else 'Profile file in Workspace → Inspect.'}

@router.get('/overview')
def overview(db: Session=Depends(get_db)):
    rows=entries(db)
    ds=[item(d,p) for d,p in rows]
    cohorts=Counter(d['cohort'] for d in ds)
    formats=Counter((d['format'] or 'not profiled') for d in ds)
    source_types=Counter(d['source_type'] for d in ds)
    profiled=[d for d in ds if d['profile_status']=='cached']
    sampled=[f for d in profiled for f in d['fields'] if f['sample_missing_pct'] is not None]
    return {'datasets':ds,'total_files':len(ds),'cohort_count':len(cohorts), 'total_bytes':sum(x['size_bytes'] for x in ds),
      'profiled_files':len(profiled),'modality_counts':category_totals(ds),'cohorts':dict(cohorts),'formats':dict(formats),'source_types':dict(source_types),
      'sampled_field_count':len(sampled),
      'sampled_missing_pct':round(sum(f['sample_missing_pct'] for f in sampled)/len(sampled),1) if sampled else None,
      'limitations':['Preview missingness is not whole-file completeness.',
                     'Counts represent source objects, not deduplicated participants.',
                     'Imaging and sequencing files are classified using extension or metadata; raw content is not decoded.',
                     'CCDI acceptance requires formal curation and authorization.']}

@router.get('/compare')
def compare(ids: str, db: Session=Depends(get_db)):
    try: wanted=list(dict.fromkeys(int(x.strip()) for x in ids.split(',') if x.strip()))
    except ValueError:raise HTTPException(422,detail='Dataset IDs must be integers.')
    if not 2<=len(wanted)<=8:raise HTTPException(422,detail='Select 2–8 datasets.')
    items=[item(d,p) for d,p in entries(db) if d.id in wanted]
    if len(items)!=len(wanted):raise HTTPException(404,detail='One or more selected datasets were not found.')
    names=[set(x['field_names']) for x in items]
    return {'datasets':items,'shared_fields':sorted(set.intersection(*names)),'union_fields':sorted(set.union(*names)),
            'unique_fields':{str(x['id']):sorted(names[i]-set.union(*(names[:i]+names[i+1:]))) if len(names)>1 else [] for i,x in enumerate(items)},
            'note':'Schema overlap only; matching names do not establish compatible meanings, units, or participant-level linkage.'}

@router.post('/explain')
def explain(body: dict,db:Session=Depends(get_db)):
    # Deliberately deterministic and grounded in cached metadata. No unsupported LLM call or clinical advice.
    question=str(body.get('question','')).strip()[:500]
    context=overview(db)
    q=question.lower()
    if not question:raise HTTPException(422,detail='Enter a question.')
    if any(k in q for k in ('missing','quality','complete')):
        answer=f"{context['profiled_files']} of {context['total_files']} files have cached profiles. "
        if context['sampled_missing_pct'] is not None:answer+=f"The unweighted mean missingness across previewed field entries is {context['sampled_missing_pct']}%. "
        answer+='This is only a sampled preview; run full validation before drawing quality conclusions.'
    elif any(k in q for k in ('cohort','dataset','file','how many')):
        answer=f"The registry contains {context['total_files']} source files across {context['cohort_count']} cohort names. {context['profiled_files']} have cached profiles."
    elif any(k in q for k in ('ccdi','submit','sync','ready')):
        answer='The CCDI preparation page builds local candidate artifacts and QC. It does not send files to CCDI. Official submission requires CCDI curator review and approved credentials.'
    else:
        answer='I can explain registered cohort/file counts, cached preview missingness, and the CCDI handoff distinction. For biological interpretation, select and validate a study first.'
    return {'answer':answer,'mode':'deterministic metadata assistant (not a generative LLM)',
            'evidence':{'profiled_files':context['profiled_files'],'total_files':context['total_files']},
            'caveat':'No raw genomic data sent to an external language model; no clinical recommendations.'}
