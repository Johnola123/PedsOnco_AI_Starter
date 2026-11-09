import io
import json
import zipfile
from pathlib import Path
from openpyxl import load_workbook
from app.ccdi import inspect_workbook, candidate_package, multi_node_candidate_package

TEMPLATE = (Path(__file__).parents[1] / 'app' / 'reference' / 'CCDI-DCC_Submission_Template_v2.2.0.xlsx').read_bytes()


def test_official_template_35_tabs_and_row2_placeholder():
    a = inspect_workbook(TEMPLATE)
    assert a['summary']['error_count'] == 0
    assert len(a['sheets']) == 32
    assert a['dictionary_property_count'] > 400
    assert a['value_set_count'] > 90
    assert all(x['nonempty_rows'] == 0 for x in a['sheets'])


def test_real_template_single_node_candidate():
    package = candidate_package(TEMPLATE, 'source.csv', b'id,race,sex,species\nP1,Unknown,Female,Homo sapiens\n',
                                'participant', {'id':'participant_id','race':'race',
                                                'sex':'sex_at_birth','species':'species'})
    with zipfile.ZipFile(io.BytesIO(package)) as z:
        wb = load_workbook(io.BytesIO(z.read('candidate_CC_DI_metadata.xlsx')))
        assert len(wb.sheetnames) == 35
        assert wb['participant']['A2'].value == 'participant'
        assert wb['participant']['C2'].value == 'P1'
        assert wb['participant']['A1'].fill.fgColor.rgb == 'FFFFCEE6'
        assert wb['Dictionary']['A1'].value == 'Property'
        assert wb['Terms and Value Sets']['A1'].value == 'Value Set Name'
        wb.close()


def test_v220_required_and_linked_record_check():
    wb=load_workbook(io.BytesIO(TEMPLATE))
    s=wb['participant']; s['A2']='participant';s['C2']='P1';s['D2']='Unknown';s['E2']='Female';s['F2']='Homo sapiens'
    d=wb['diagnosis']; d['A2']='diagnosis';d['B2']='NO_SUCH_PARTICIPANT';d['D2']='D1'
    out=io.BytesIO();wb.save(out);wb.close()
    codes={x['code'] for x in inspect_workbook(out.getvalue(),check_values=True)['issues']}
    assert 'BROKEN_RELATIONSHIP' in codes
    assert 'REQUIRED_VALUE_MISSING' in codes


def test_v220_multinode_package():
    inp=io.BytesIO()
    with zipfile.ZipFile(inp,'w') as z:
        z.writestr('participants.csv','id,race,sex,species\nP1,Unknown,Female,Homo sapiens\n')
        z.writestr('diagnoses.csv','pid,did,diagnosis\nP1,D1,Neuroblastoma\n')
    mapping={'participant':{'file':'participants.csv','mappings':{'id':'participant_id','race':'race','sex':'sex_at_birth','species':'species'}},
             'diagnosis':{'file':'diagnoses.csv','mappings':{'pid':'participant.participant_id','did':'diagnosis_id','diagnosis':'submitted_diagnosis'}}}
    z=multi_node_candidate_package(TEMPLATE,inp.getvalue(),mapping,source_accession='TEST-DEMO')
    with zipfile.ZipFile(io.BytesIO(z)) as out:
        wb=load_workbook(io.BytesIO(out.read('candidate_CC_DI_metadata.xlsx')))
        assert wb['participant']['C2'].value=='P1'
        assert wb['diagnosis']['B2'].value=='P1'
        assert wb['diagnosis']['A2'].value=='diagnosis'
        report=json.loads(out.read('validation_report.json'))
        assert not any(i['code']=='BROKEN_RELATIONSHIP' for i in report['issues'])
        meta=json.loads(out.read('provenance_manifest.json'))
        assert meta['transfer_to_ccdi'] is False
        assert len(meta['nodes'])==2
        wb.close()
