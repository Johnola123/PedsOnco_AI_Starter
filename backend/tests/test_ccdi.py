import csv
import io
import json
import zipfile
from openpyxl import Workbook, load_workbook
from app.ccdi import REQUIRED_NODES, inspect_workbook, candidate_package


def template_bytes():
    wb = Workbook(); wb.remove(wb.active)
    for node in REQUIRED_NODES:
        ws = wb.create_sheet(node)
        ws.append(['participant_id', 'diagnosis', 'study_id'])
    data = io.BytesIO(); wb.save(data)
    return data.getvalue()


def test_template_nodes():
    result = inspect_workbook(template_bytes())
    assert result['summary']['error_count'] == 0
    assert len(result['sheets']) == 8
    assert result['status'] == 'preliminary-review-required'


def test_missing_nodes():
    wb = Workbook(); wb.active.title = 'participant'; wb.active.append(['participant_id', 'study_id'])
    data = io.BytesIO(); wb.save(data)
    result = inspect_workbook(data.getvalue())
    assert result['summary']['error_count'] == 7


def test_candidate_zip_round_trip():
    source = b'patient_id,disease\np01,Neuroblastoma\np02,Neuroblastoma\n'
    package = candidate_package(template_bytes(), 'clinical.csv', source, 'participant',
                                {'patient_id':'participant_id', 'disease':'diagnosis'}, source_accession='TEST')
    with zipfile.ZipFile(io.BytesIO(package)) as zipped:
        assert set(zipped.namelist()) == {'candidate_CC_DI_metadata.xlsx','validation_report.json','provenance_manifest.json','README.txt'}
        wb = load_workbook(io.BytesIO(zipped.read('candidate_CC_DI_metadata.xlsx')))
        assert wb['participant']['A2'].value == 'p01'
        assert wb['participant']['B3'].value == 'Neuroblastoma'
        p = json.loads(zipped.read('provenance_manifest.json'))
        assert p['record_count'] == 2
        assert p['source_accession'] == 'TEST'


def test_unrecognized_target_rejected():
    import pytest
    with pytest.raises(ValueError):
        candidate_package(template_bytes(), 'data.csv', b'id\na\n', 'participant', {'id':'not_a_property'})
