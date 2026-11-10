"""Public, read-only repository discovery. No restricted patient-level data or CCDI submission."""
import re
from urllib.parse import quote, urljoin, urlparse, unquote
from html.parser import HTMLParser
import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix='/api/discovery', tags=['Public repository explorer'])
BASE_GDC = 'https://api.gdc.cancer.gov'
EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
SOURCES = [
 {'id':'geo','name':'NCBI GEO','mode':'live-search-and-processed-file-import','modalities':['expression','epigenomics'],'url':'https://www.ncbi.nlm.nih.gov/geo/'},
 {'id':'gdc','name':'NCI GDC / TARGET','mode':'live-search-and-open-file-import','modalities':['genomics','transcriptomics','clinical'],'url':'https://portal.gdc.cancer.gov/'},
 {'id':'tcia','name':'TCIA','mode':'live-metadata-discovery','modalities':['radiology','pathology'],'url':'https://www.cancerimagingarchive.net/'},
 {'id':'stjude','name':'St. Jude Cloud','mode':'curated-public-portal','modalities':['pediatric genomics','expression'],'url':'https://www.stjude.cloud/'},
 {'id':'ccdi','name':'CCDI Data Federation / C3DC','mode':'live-federation-metadata','modalities':['pediatric clinical and molecular metadata'],'url':'https://ccdi.cancer.gov/'},
 {'id':'sra','name':'NCBI Sequence Read Archive','mode':'external-discovery','modalities':['sequencing'],'url':'https://www.ncbi.nlm.nih.gov/sra'},
 {'id':'kidsfirst','name':'Kids First Data Resource','mode':'external-discovery','modalities':['pediatric genomics','clinical'],'url':'https://portal.kidsfirstdrc.org/'},
 {'id':'dbgap','name':'dbGaP','mode':'metadata-only-external-discovery','modalities':['genotypes','phenotypes'],'url':'https://www.ncbi.nlm.nih.gov/gap/'},
]

def clean_term(term: str) -> str:
    term = term.strip()
    if not term or len(term)>120 or any(ord(c)<32 for c in term):
        raise HTTPException(422, detail='Enter a search term of 1–120 printable characters.')
    return term

async def fetch_json(url: str, params: dict):
    try:
        async with httpx.AsyncClient(timeout=18, follow_redirects=False) as client:
            r = await client.get(url, params=params, headers={'User-Agent':'CCDI-Track1-research-demo/1.0'})
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, detail='Repository temporarily unavailable. Retry or use its public portal.') from exc

@router.get('/sources')
def sources():
    return {'sources':SOURCES, 'note':'External discovery is not direct data import or authorized CCDI submission.'}

@router.get('/search')
async def search(source: str, q: str, limit: int=Query(10,ge=1,le=30)):
    term = clean_term(q)
    source = source.lower()
    if source == 'geo':
        search_data = await fetch_json(EUTILS+'/esearch.fcgi', {'db':'gds','term':f'({term}) AND gse[ETYP]','retmode':'json','retmax':limit})
        ids = search_data.get('esearchresult',{}).get('idlist',[])
        if not ids:
            return {'source':'geo','items':[],'count':0}
        details = await fetch_json(EUTILS+'/esummary.fcgi', {'db':'gds','id':','.join(ids),'retmode':'json'})
        result=details.get('result',{})
        items=[]
        for uid in ids:
            doc=result.get(str(uid),{})
            acc=doc.get('accession','')
            if not str(acc).startswith('GSE'): continue
            items.append({'id':acc,'title':doc.get('title') or acc,'summary':str(doc.get('summary') or '')[:1200],
              'organism':doc.get('taxon') or '', 'sample_count':doc.get('n_samples') or doc.get('samples') or None,
              'modality':doc.get('gdstype') or 'GEO study', 'link':f'https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}',
              'access':'metadata only; review individual files before importing'})
        return {'source':'geo','items':items,'count':int(search_data.get('esearchresult',{}).get('count',0))}
    if source == 'gdc':
        # GDC project search: use public project identifiers, avoid downloading restricted data.
        filters={'op':'or','content':[{'op':'contains','content':{'field':'project_id','value':term}}, {'op':'contains','content':{'field':'name','value':term}}]}
        data=await fetch_json(BASE_GDC+'/projects', {'filters':__import__('json').dumps(filters),'fields':'project_id,name,primary_site,disease_type,summary','size':limit,'format':'JSON'})
        hits=data.get('data',{}).get('hits',[])
        return {'source':'gdc','items':[{'id':v.get('project_id'),'title':v.get('name') or v.get('project_id'),
          'summary':', '.join(v.get('disease_type') or []), 'organism':'human','sample_count':(v.get('summary') or {}).get('case_count'),
          'modality':'molecular / clinical', 'link':'https://portal.gdc.cancer.gov/projects/'+str(v.get('project_id')),
          'access':'mixed: inspect each file access level'} for v in hits], 'count':data.get('data',{}).get('pagination',{}).get('total',len(hits))}
    raise HTTPException(422,detail='Live in-app search currently supports GEO and GDC. Other sources have verified portal links.')

@router.get('/geo/{accession}')
async def geo_detail(accession: str):
    accession=accession.upper()
    if not re.fullmatch(r'GSE\d{1,12}',accession): raise HTTPException(422, detail='Expected GEO Series accession GSE12345.')
    search_data=await fetch_json(EUTILS+'/esearch.fcgi',{'db':'gds','term':f'{accession}[ACCN]','retmode':'json','retmax':6})
    ids=search_data.get('esearchresult',{}).get('idlist',[])
    if not ids: raise HTTPException(404,detail='GEO accession not found.')
    result=(await fetch_json(EUTILS+'/esummary.fcgi',{'db':'gds','id':','.join(ids),'retmode':'json'})).get('result',{})
    doc=next((result.get(str(i),{}) for i in ids if result.get(str(i),{}).get('accession')==accession),None)
    if not doc: raise HTTPException(404,detail='No exact GEO Series match.')
    return {'source':'geo','accession':accession,'title':doc.get('title'),'summary':doc.get('summary'),
      'organism':doc.get('taxon'),'sample_count':doc.get('n_samples'),'platform':doc.get('gpl'),'record':doc,
      'file_candidates':[], 'link':f'https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={accession}',
      'note':'Discover metadata here; choose a permitted processed file at GEO and use its HTTPS URL with Add data → External URL. No raw SRA/controlled download is automated.'}

@router.get('/gdc/{project_id}/files')
async def gdc_files(project_id: str, limit: int=Query(25,ge=1,le=100)):
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,50}',project_id): raise HTTPException(422,detail='Invalid project ID')
    import json
    filters={'op':'and','content':[{'op':'in','content':{'field':'cases.project.project_id','value':[project_id]}},
                              {'op':'in','content':{'field':'access','value':['open']}}]}
    data=await fetch_json(BASE_GDC+'/files',{'filters':json.dumps(filters),'fields':'file_id,file_name,data_type,data_format,access,file_size,md5sum','size':limit,'format':'JSON'})
    hits=data.get('data',{}).get('hits',[])
    return {'source':'gdc','project_id':project_id,'count':data.get('data',{}).get('pagination',{}).get('total',len(hits)),
      'files':[{'id':v.get('file_id') or v.get('id'),'name':v.get('file_name'),'format':v.get('data_format'),
        'data_type':v.get('data_type'),'access':v.get('access'),'size':v.get('file_size'), 'md5':v.get('md5sum'),
        'download_url':f"{BASE_GDC}/data/{v.get('file_id') or v.get('id')}"} for v in hits],
      'note':'Only files reported by GDC as open access are listed for automatic import. Large downloads remain subject to application size limits.'}

@router.get('/gdc/file/{file_id}/verify')
async def verify_gdc_file(file_id: str):
    if not re.fullmatch(r'[0-9a-fA-F-]{36}',file_id): raise HTTPException(422,detail='Invalid GDC file identifier')
    data=await fetch_json(f'{BASE_GDC}/files/{file_id}',{'fields':'file_id,file_name,access,file_size,data_format,md5sum'})
    item=data.get('data',{})
    if item.get('access')!='open':raise HTTPException(403,detail='Restricted file: direct import is prohibited.')
    return {'id':file_id,'name':item.get('file_name'),'access':'open','size':item.get('file_size'),
            'download_url':f'{BASE_GDC}/data/{file_id}'}


# GEO accession endpoints never accept arbitrary remote URLs. Directory listings
# are fetched only from a fixed NCBI HTTPS origin; candidate names are validated.
GEO_HOST = 'https://ftp.ncbi.nlm.nih.gov'
GEO_FILE_EXT = ('.txt', '.txt.gz', '.csv', '.csv.gz', '.tsv', '.tsv.gz', '.xlsx', '.soft.gz')
GEO_SERIES_RE = re.compile(r'GSE[0-9]{1,12}\Z')

class _DirectoryLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href=dict(attrs).get('href','')
            if href: self.links.append(href)

def geo_series_path(accession: str) -> str:
    accession=accession.upper()
    if not GEO_SERIES_RE.fullmatch(accession):
        raise HTTPException(422, detail='Use a GEO Series accession such as GSE12345.')
    return f'/geo/series/{accession[:-3]}nnn/{accession}/'

def validated_geo_candidate(accession: str, folder: str, filename: str) -> str:
    if folder not in ('matrix','suppl'):
        raise HTTPException(422, detail='Only GEO Series matrix and supplementary folders are supported.')
    filename=unquote(filename)
    if not filename.startswith(accession.upper()+'_') or not re.fullmatch(r'[a-zA-Z0-9_.+-]{1,220}',filename):
        raise HTTPException(422,detail='Invalid GEO processed-file name.')
    if not filename.lower().endswith(GEO_FILE_EXT):
        raise HTTPException(422,detail='Only selected processed data formats can be imported.')
    return GEO_HOST+geo_series_path(accession)+folder+'/'+quote(filename)

async def geo_directory(accession: str, folder: str):
    directory=GEO_HOST+geo_series_path(accession)+folder+'/'
    try:
        async with httpx.AsyncClient(timeout=18,follow_redirects=False) as client:
            r=await client.get(directory,headers={'User-Agent':'CCDI-Track1-research-demo/1.0'})
            r.raise_for_status()
            if len(r.content)>1_000_000:raise HTTPException(502,detail='GEO directory listing too large.')
            parser=_DirectoryLinks();parser.feed(r.text)
    except httpx.HTTPError as exc:
        raise HTTPException(502,detail='GEO file listing unavailable; inspect the source accession directly.') from exc
    names=[]
    for href in parser.links:
        name=unquote(href.split('?',1)[0])
        try:
            url=validated_geo_candidate(accession,folder,name)
        except HTTPException:continue
        if url not in [x['download_url'] for x in names]:
            names.append({'id':f'{folder}:{name}','name':name,'format':name.rsplit('.',1)[-1],
                'data_type':'GEO processed / supplementary file','access':'public','size':None,
                'download_url':url,'folder':folder,'preview_supported':name.lower().endswith(('.csv','.tsv','.xlsx','.txt'))})
        if len(names)>=100:break
    return names

@router.get('/geo/{accession}/files')
async def geo_files(accession: str):
    accession=accession.upper()
    geo_series_path(accession)
    files=[];warnings=[]
    for folder in ('matrix','suppl'):
        try: files+=await geo_directory(accession,folder)
        except HTTPException as exc:warnings.append(f'{folder}: {exc.detail}')
    return {'source':'geo','accession':accession,'files':files,'count':len(files),'warnings':warnings,
        'note':'Files are public GEO candidates, not verified CCDI-ready data. .gz files are stored as compressed files and may require decompression before profiling. No raw sequencing files are fetched.'}

TCIA_BASE='https://services.cancerimagingarchive.net/services/v4/TCIA/query'

@router.get('/tcia/collections')
async def tcia_collections(q: str='',limit:int=Query(30,ge=1,le=100)):
    # TCIA v4 public query API; metadata discovery only, never bulk image transfer.
    term=q.strip().lower()
    if len(term)>120:raise HTTPException(422,detail='Search is too long.')
    data=await fetch_json(TCIA_BASE+'/getCollectionValues',{'format':'json'})
    if not isinstance(data,list):raise HTTPException(502,detail='Unexpected TCIA API response.')
    items=[]
    for x in data:
        name=x.get('Collection') or x.get('collection') or ''
        if name and term in name.lower():
            items.append({'id':name,'title':name,'summary':'TCIA imaging collection (metadata only)',
              'modality':'radiology / imaging','link':'https://www.cancerimagingarchive.net/',
              'access':'Public collection metadata; individual series permissions may vary',
              'sample_count':None})
    return {'source':'tcia','items':items[:limit],'count':len(items),'note':'Collection results are not participant counts.'}

@router.get('/tcia/{collection}/summary')
async def tcia_summary(collection: str):
    if not re.fullmatch(r'[a-zA-Z0-9_. -]{2,100}',collection):raise HTTPException(422,detail='Invalid collection')
    data=await fetch_json(TCIA_BASE+'/getModalityValues',{'Collection':collection,'format':'json'})
    modalities=[str(x.get('Modality') or x.get('modality') or '') for x in data] if isinstance(data,list) else []
    return {'source':'tcia','collection':collection,'modalities':sorted(set(filter(None,modalities))),
      'note':'Imaging metadata overview; downloading and de-identifying DICOM are not implemented.'}

FEDERATION='https://ccdi.stjude.cloud/api/v1'
@router.get('/ccdi/organizations')
async def ccdi_organizations(q: str='', limit:int=Query(30,ge=1,le=100)):
    term=q.strip().lower()
    if len(term)>120:raise HTTPException(422,detail='Search is too long.')
    payload=await fetch_json(FEDERATION+'/organization',{})
    # Federation nodes can wrap results differently; explicitly flag unknown shapes.
    entries=payload if isinstance(payload,list) else payload.get('results',payload.get('organizations',[])) if isinstance(payload,dict) else []
    if not isinstance(entries,list):raise HTTPException(502,detail='Unexpected federation API response.')
    items=[]
    for obj in entries:
        if not isinstance(obj,dict):continue
        ident=obj.get('identifier',{})
        name=(ident.get('name') if isinstance(ident,dict) else '') or obj.get('name') or str(ident)
        if term in name.lower():items.append({'id':name,'title':name,'summary':'Participating organization metadata',
            'modality':'federated metadata', 'link':'https://ccdi.stjude.cloud/',
            'access':'Discovery only, no CCDI deposition', 'sample_count':None})
    return {'source':'ccdi','items':items[:limit],'count':len(items),'note':'Federation discovery is not an authorized data-submission endpoint.'}
