import asyncio
import pytest
from fastapi import HTTPException
from app import discovery


def test_geo_path_and_filename_constraints():
    assert discovery.geo_series_path('GSE12345') == '/geo/series/GSE12nnn/GSE12345/'
    url=discovery.validated_geo_candidate('GSE12345','matrix','GSE12345_series_matrix.txt.gz')
    assert url.startswith('https://ftp.ncbi.nlm.nih.gov/geo/series/GSE12nnn/')
    for name in ('../../etc/passwd','GSE12345_secrets.zip','GSE12345_x.fastq.gz'):
        with pytest.raises(HTTPException): discovery.validated_geo_candidate('GSE12345','matrix',name)
    with pytest.raises(HTTPException):discovery.geo_series_path('GSE1/../../')


def test_geo_file_listing_and_permitted_files(monkeypatch):
    class Response:
        content=b'<a href="../">parent</a><a href="GSE12345_series_matrix.txt.gz">matrix</a><a href="GSE12345_RAW.tar">raw</a>'
        text=content.decode()
        def raise_for_status(self):return None
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def get(self,url,**kwargs):return Response()
    monkeypatch.setattr(discovery.httpx,'AsyncClient',lambda **kwargs:Client())
    files=asyncio.run(discovery.geo_directory('GSE12345','matrix'))
    assert len(files)==1
    assert files[0]['id']=='matrix:GSE12345_series_matrix.txt.gz'


def test_tcia_collection_filter(monkeypatch):
    async def fake(url, params):
        assert '/getCollectionValues' in url
        return [{'Collection':'TARGET-NBL'},{'Collection':'TCGA-GBM'}]
    monkeypatch.setattr(discovery,'fetch_json',fake)
    result=asyncio.run(discovery.tcia_collections('nbl',30))
    assert [x['id'] for x in result['items']]==['TARGET-NBL']


def test_ccdi_federation_organization_parser(monkeypatch):
    async def fake(url,params):
        return {'organizations':[{'identifier':{'name':'Example Institute'}},{'identifier':{'name':'Other'}}]}
    monkeypatch.setattr(discovery,'fetch_json',fake)
    x=asyncio.run(discovery.ccdi_organizations('example',30))
    assert x['items'][0]['id']=='Example Institute'
    assert x['count']==1


def test_gzip_metadata_preview_bounded(monkeypatch):
    import io, gzip
    from app import profiling
    raw=b'participant_id\tage\nA\t12\nB\t\n'
    class Obj:
        def get_object(self,**kwargs):return {'Body':io.BytesIO(gzip.compress(raw))}
    monkeypatch.setattr(profiling,'get_s3_client',lambda:Obj())
    x=profiling._compressed_text_preview('key','GSE123_processed.tsv.gz')
    assert x['profile_mode']=='bounded_gzip_decompressed_preview'
    assert x['row_count_complete'] is False
    assert x['tables'][0]['rows'] is None
    assert x['tables'][0]['fields'][0]['name']=='participant_id'
