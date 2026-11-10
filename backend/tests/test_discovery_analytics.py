import asyncio
from types import SimpleNamespace
from fastapi import HTTPException
import pytest
from app import discovery, analytics


def test_sources_have_honest_integration_status():
    data=discovery.sources()
    modes={x['id']:x['mode'] for x in data['sources']}
    assert modes['geo']=='live-search-and-processed-file-import'
    assert modes['gdc']=='live-search-and-open-file-import'
    assert modes['tcia']=='live-metadata-discovery'
    assert modes['ccdi']=='live-federation-metadata'


def test_search_input_validation():
    with pytest.raises(HTTPException):
        discovery.clean_term('')
    with pytest.raises(HTTPException):
        discovery.clean_term('X'*121)


def test_geo_search_summary(monkeypatch):
    async def fake(url,params):
        if 'esearch' in url:return {'esearchresult':{'idlist':['123'],'count':'1'}}
        return {'result':{'123':{'accession':'GSE456','title':'Pediatric RNA study','summary':'Test summary','taxon':'Homo sapiens'}}}
    monkeypatch.setattr(discovery,'fetch_json',fake)
    result=asyncio.run(discovery.search('geo','neuroblastoma',5))
    assert result['items'][0]['id']=='GSE456'
    assert result['items'][0]['title']=='Pediatric RNA study'


def test_gdc_open_access_file_filter(monkeypatch):
    async def fake(url,params):
        assert '"open"' in params['filters']
        return {'data':{'hits':[{'file_id':'abcd','file_name':'public.tsv','access':'open','file_size':1024}]}}
    monkeypatch.setattr(discovery,'fetch_json',fake)
    result=asyncio.run(discovery.gdc_files('TARGET-NBL',10))
    assert result['files'][0]['download_url'].endswith('/abcd')


def test_gdc_restricted_file_rejected(monkeypatch):
    async def fake(url,params):return {'data':{'access':'controlled'}}
    monkeypatch.setattr(discovery,'fetch_json',fake)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(discovery.verify_gdc_file('12345678-1234-1234-1234-123456789abc'))
    assert exc.value.status_code==403


def test_cached_preview_field_stats():
    data={'tables':[{'name':'clinical','preview':[['patient_id','age'],['x',''],['y',23]],
                     'fields':[{'name':'patient_id','inferred_type':'string'},{'name':'age','inferred_type':'integer'}]}]}
    fs=analytics.fields(data)
    assert fs['clinical.age']['sample_missing_pct']==50
    assert fs['clinical.patient_id']['sample_missing_pct']==0
    assert analytics.fields(None)=={}


def test_schema_union_comparison_not_patient_linkage(monkeypatch):
    rows=[(SimpleNamespace(id=i,project_name='C',original_name=f'{i}.csv',size_bytes=4,source=None),
           {'tables':[{'name':'data','preview':[['id','value'],['x','1']],
                       'fields':[{'name':'id','inferred_type':'string'}, {'name':'value' if i==1 else 'other','inferred_type':'string'}]}]}) for i in (1,2)]
    monkeypatch.setattr(analytics,'entries',lambda db:rows)
    result=analytics.compare('1,2',db=None)
    assert result['shared_fields']==['id']
    assert 'compatible meanings' in result['note']
