"""Conservative CCDI workbook tools. Template version is user supplied; no false certification."""
import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

REQUIRED_NODES = ('study', 'study_admin', 'study_funding', 'study_personnel',
                  'publication', 'consent_group', 'participant', 'diagnosis')
REFERENCE_NAMES = {'readme', 'instructions', 'dictionary', 'terms and value sets'}


def _is_reference(name: str) -> bool:
    low = name.strip().lower()
    return any(token in low for token in REFERENCE_NAMES) or low.startswith('terms')


def _headers(ws):
    """Locate property/header row from typical CCDI templates; return one-based row & labels.

    CCDI templates differ across versions; ambiguous header placement is flagged for manual review.
    """
    candidates = []
    for row in ws.iter_rows(min_row=1, max_row=min(12, ws.max_row or 1), max_col=min(ws.max_column or 1, 300)):
        cells = [str(c.value).strip() if c.value is not None else '' for c in row]
        labels = [v for v in cells if v]
        if len(labels) < 2:
            continue
        score = sum(1 for v in labels if re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', v))
        if score >= 2:
            candidates.append((score, -row[0].row, row[0].row, cells))
    if not candidates:
        return None, [], ['Could not reliably detect header row; inspect workbook manually.']
    _, _, idx, names = max(candidates)
    warnings = []
    if idx != 1:
        warnings.append(f'Headers detected on row {idx}; confirm this is the CCDI property row.')
    if len(set(name for name in names if name)) != len([name for name in names if name]):
        warnings.append('Duplicate column headers detected.')
    return idx, names, warnings


def _data_rows(ws, headers):
    """Ignore CCDI's row-2 prefilled node type when other fields are blank."""
    type_column = next((i for i, h in enumerate(headers) if h == 'type'), None)
    for row_number, row in enumerate(ws.iter_rows(min_row=2, max_row=min(ws.max_row, 10002), values_only=True), 2):
        values = list(row)
        if type_column is not None and type_column < len(values):
            values[type_column] = None
        if any(v is not None and str(v).strip() for v in values):
            yield row_number, row


def _dictionary(wb):
    output = {}
    if 'Dictionary' not in wb:
        return output
    ws = wb['Dictionary']
    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 7 or not row[0] or not row[2]:
            continue
        key = (str(row[2]).strip().lower(), str(row[0]).strip())
        output[key] = {'type': str(row[3] or ''), 'example': str(row[4] or ''),
                       'required': str(row[5] or ''), 'key': str(row[6] or '')}
    return output


def _terms(wb):
    output = {}
    if 'Terms and Value Sets' not in wb:
        return output
    for row in wb['Terms and Value Sets'].iter_rows(min_row=2, max_col=3, values_only=True):
        if row[0] and row[2]:
            output.setdefault(str(row[0]).strip(), set()).add(str(row[2]).strip())
    return output


def inspect_workbook(data: bytes, *, check_values: bool = False) -> dict[str, Any]:
    if len(data) > 20 * 1024 * 1024:
        raise ValueError('Metadata workbook exceeds 20 MiB; contact the tool maintainer about this limit.')
    wb = load_workbook(io.BytesIO(data), read_only=False, data_only=True)
    try:
        dictionary = _dictionary(wb)
        terms = _terms(wb)
        issues = []
        result = {'sheets': [], 'issues': issues, 'required_nodes': list(REQUIRED_NODES),
                  'template_sha256': hashlib.sha256(data).hexdigest(),
                  'mode': 'populated-workbook-check' if check_values else 'template-inspection',
                  'validated_against_live_ccdi': False,
                  'dictionary_property_count': len(dictionary), 'value_set_count': len(terms),
                  'validation_scope': 'local workbook model checks, not CCDI curator acceptance'}
        available = {ws.title.strip().lower() for ws in wb.worksheets}
        for node in REQUIRED_NODES:
            if node not in available:
                issues.append({'level':'error','code':'MISSING_REQUIRED_SHEET','sheet':node,
                               'message':f'Missing core node sheet: {node}'})
        all_rows = {}
        all_headers = {}
        for ws in wb.worksheets:
            if _is_reference(ws.title):
                continue
            hdr_idx, headers, warnings = _headers(ws)
            cols = [{'name': h, 'column': i + 1,
                     'required': bool(ws.cell(1, i+1).fill.fgColor.rgb in ('00FFF2CC','FFFFF2CC')),
                     'relationship': '.' in h,
                     'datatype': dictionary.get((ws.title.lower(), h), {}).get('type', ''),
                     'allowed_count': len(terms.get(h, ())) }
                    for i, h in enumerate(headers) if h]
            for warning in warnings:
                issues.append({'level':'warning','code':'HEADER_REVIEW','sheet':ws.title,'message':warning})
            rows = list(_data_rows(ws, headers)) if hdr_idx == 1 else []
            all_rows[ws.title.lower()] = rows
            all_headers[ws.title.lower()] = headers
            result['sheets'].append({'name':ws.title,'header_row':hdr_idx,'fields':cols,
                                     'nonempty_rows':len(rows),'total_rows_inspected': min(ws.max_row, 10002),
                                     'mandatory_columns': [c['name'] for c in cols if c['required']]})
            if ws.max_row > 10002:
                issues.append({'level':'warning','code':'ROW_LIMIT','sheet':ws.title,
                               'message':'Only the first 10,001 data rows were checked.'})
            if check_values and ws.title.lower() in REQUIRED_NODES and not rows:
                issues.append({'level':'warning','code':'CORE_NODE_EMPTY','sheet':ws.title,
                               'message':'Core sheet has no completed metadata records.'})
        if check_values:
            keys = {}
            for name, rows in all_rows.items():
                headers = all_headers[name]
                for i, field in enumerate(headers):
                    if field and field.endswith('_id') and '.' not in field:
                        keys[(name,field)] = {str(row[i]).strip() for _,row in rows if i<len(row) and row[i] is not None and str(row[i]).strip()}
            for name, rows in all_rows.items():
                ws=wb[name]
                headers=all_headers[name]
                for rowno, row in rows:
                    for i,field in enumerate(headers):
                        if not field:
                            continue
                        value=row[i] if i<len(row) else None
                        value_str=str(value).strip() if value is not None else ''
                        cell=ws.cell(row=1,column=i+1)
                        yellow=cell.fill.fgColor.rgb in ('00FFF2CC','FFFFF2CC')
                        if yellow and not value_str:
                            if len(issues)<250:
                                issues.append({'level':'error','code':'REQUIRED_VALUE_MISSING','sheet':name,'row':rowno,
                                               'field':field,'message':f'Row {rowno}: mandatory {field} is blank'})
                            continue
                        if not value_str:
                            continue
                        if field=='type' and value_str.lower()!=name:
                            issues.append({'level':'error','code':'INVALID_NODE_TYPE','sheet':name,'row':rowno,
                                           'field':field,'message':f'Expected type={name}, observed {value_str}'})
                        if '.' in field:
                            related, key = field.split('.',1)
                            accepted=keys.get((related,key))
                            if accepted is not None and value_str not in accepted and len(issues)<250:
                                issues.append({'level':'error','code':'BROKEN_RELATIONSHIP','sheet':name,'row':rowno,
                                               'field':field,'message':f'Unknown {related}.{key}: {value_str}'})
                        d=dictionary.get((name,field),{})
                        enumvalues=terms.get(field)
                        if enumvalues and d.get('type','').lower() in ('enum','string') and value_str not in enumvalues and len(issues)<250:
                            issues.append({'level':'error','code':'INVALID_CONTROLLED_TERM','sheet':name,'row':rowno,
                                           'field':field,'message':f'Value {value_str!r} not in workbook value set for {field}'})
                        elif d.get('type','').lower()=='integer':
                            try:
                                if float(value_str)!=int(float(value_str)): raise ValueError()
                            except (ValueError, OverflowError):
                                issues.append({'level':'error','code':'INVALID_INTEGER','sheet':name,'row':rowno,
                                               'field':field,'message':f'Expected integer for {field}'})
        result['summary']={'sheet_count':len(result['sheets']),
                           'error_count':sum(i['level']=='error' for i in issues),
                           'warning_count':sum(i['level']=='warning' for i in issues),
                           'issue_list_truncated':len(issues)>=250}
        result['status']='structural-errors' if result['summary']['error_count'] else 'preliminary-review-required'
        return result
    finally:
        wb.close()


def _source_rows(name: str, data: bytes):
    suffix = Path(name).suffix.lower()
    if suffix not in ('.csv', '.tsv'):
        raise ValueError('Candidate export currently supports CSV/TSV source tables only.')
    if len(data) > 10 * 1024 * 1024:
        raise ValueError('Candidate source table must be no larger than 10 MiB.')
    text = data.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text), delimiter='\t' if suffix == '.tsv' else ',')
    if not reader.fieldnames:
        raise ValueError('Source table has no header.')
    rows = []
    for idx, row in enumerate(reader):
        if idx >= 5000:
            raise ValueError('Candidate preview/export limited to 5000 rows.')
        rows.append(row)
    return reader.fieldnames, rows


def candidate_package(template: bytes, source_name: str, source_bytes: bytes, node: str,
                      mappings: dict[str, str], *, source_accession: str = '') -> bytes:
    if not mappings:
        raise ValueError('Supply at least one reviewed source-to-target mapping.')
    inspection = inspect_workbook(template)
    if inspection['summary']['error_count']:
        raise ValueError('Template is missing required CCDI sheets; check the supplied official template.')
    wb = load_workbook(io.BytesIO(template))
    try:
        target = next((s for s in wb.worksheets if s.title.lower() == node.lower()), None)
        if target is None or _is_reference(target.title):
            raise ValueError('Requested target CCDI node was not found in template.')
        hdr_idx, headers, warnings = _headers(target)
        if not hdr_idx:
            raise ValueError('Could not identify target node headers. Check the CCDI template version.')
        indices = {header: idx + 1 for idx, header in enumerate(headers) if header}
        source_headers, records = _source_rows(source_name, source_bytes)
        if any(k not in source_headers for k in mappings):
            raise ValueError('At least one mapping source field is not in the input CSV/TSV.')
        if any(v not in indices or v == 'type' for v in mappings.values()):
            raise ValueError('At least one mapping target is absent in CCDI node headers.')
        if len(set(mappings.values())) != len(mappings):
            raise ValueError('Multiple source fields target the same CCDI property.')
        # CCDI official templates contain a node-type placeholder in A2. It is not a data row.
        if list(_data_rows(target, headers)):
            raise ValueError('Target sheet already contains metadata; use a blank template.')
        for ridx, record in enumerate(records, start=hdr_idx + 1):
            if 'type' in indices:
                target.cell(row=ridx, column=indices['type'], value=target.title)
            for src, dst in mappings.items():
                target.cell(row=ridx, column=indices[dst], value=record.get(src) or None)
        generated = io.BytesIO()
        wb.save(generated)
        enriched = generated.getvalue()
        report = inspect_workbook(enriched, check_values=True)
        report['mapping'] = mappings
        report['source_name'] = source_name
        report['source_accession'] = source_accession
        report['disclaimer'] = 'Candidate metadata only. No certification of CCDI controlled vocabulary, consent, or upload readiness.'
        provenance = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
                      'source_name': source_name, 'source_accession': source_accession,
                      'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
                      'ccdi_template_sha256': hashlib.sha256(template).hexdigest(),
                      'candidate_workbook_sha256': hashlib.sha256(enriched).hexdigest(),
                      'target_node': node, 'mappings': mappings, 'record_count': len(records)}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('candidate_CC_DI_metadata.xlsx', enriched)
            z.writestr('validation_report.json', json.dumps(report, indent=2))
            z.writestr('provenance_manifest.json', json.dumps(provenance, indent=2))
            z.writestr('README.txt', 'Candidate mapping package for CCDI curation. NOT a validated CCDI submission.\n'
                         'Provide study administration, consent, required fields and value-set review before submitting.\n')
        return buffer.getvalue()
    finally:
        wb.close()


def multi_node_candidate_package(template: bytes, source_zip: bytes, configuration: dict, *, source_accession: str = '') -> bytes:
    """CSV/TSV files in one ZIP mapped to multiple CCDI sheets; no network transfer."""
    if not isinstance(configuration, dict) or not configuration:
        raise ValueError('Provide a mapping JSON object keyed by CCDI node.')
    if len(source_zip)>30*1024*1024:
        raise ValueError('Source ZIP must be at most 30 MiB for this proof of concept.')
    wb=load_workbook(io.BytesIO(template))
    provenance=[]
    try:
        with zipfile.ZipFile(io.BytesIO(source_zip)) as srczip:
            for node, config in configuration.items():
                if not isinstance(config,dict) or not isinstance(config.get('mappings'),dict):
                    raise ValueError(f'{node}: expected file and mappings object')
                filename=config.get('file')
                if not isinstance(filename,str) or filename not in srczip.namelist() or '..' in filename or filename.startswith('/'):
                    raise ValueError(f'{node}: file not found or unsafe ZIP path')
                if srczip.getinfo(filename).file_size>10*1024*1024:
                    raise ValueError(f'{filename}: exceeds 10 MiB import limit')
                ws=next((s for s in wb.worksheets if s.title.lower()==node.lower() and not _is_reference(s.title)),None)
                if ws is None: raise ValueError(f'Unknown CCDI node: {node}')
                hdr,headers,_=_headers(ws)
                if hdr!=1 or list(_data_rows(ws,headers)):
                    raise ValueError(f'{node}: expected blank CCDI sheet with headers in row 1')
                indices={h:i+1 for i,h in enumerate(headers) if h}
                source=srczip.read(filename)
                srcfields,rows=_source_rows(filename, source)
                mappings=config['mappings']
                if not mappings or any(k not in srcfields or v not in indices or v=='type' for k,v in mappings.items()):
                    raise ValueError(f'{node}: mapping contains nonexistent source/target or reserved type')
                if len(set(mappings.values()))!=len(mappings):
                    raise ValueError(f'{node}: duplicate destination columns')
                for rowno,record in enumerate(rows,2):
                    if 'type' in indices: ws.cell(rowno,indices['type'],node)
                    for sourcefield,targetfield in mappings.items():
                        ws.cell(rowno,indices[targetfield],record.get(sourcefield) or None)
                provenance.append({'node':node,'file':filename,'rows':len(rows),
                                   'sha256':hashlib.sha256(source).hexdigest(),'mappings':mappings})
        buf=io.BytesIO();wb.save(buf); candidate=buf.getvalue()
        report=inspect_workbook(candidate,check_values=True)
        meta={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'source_accession':source_accession,
              'template_sha256':hashlib.sha256(template).hexdigest(),'candidate_sha256':hashlib.sha256(candidate).hexdigest(),
              'nodes':provenance,'transfer_to_ccdi':False}
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('candidate_CC_DI_metadata.xlsx',candidate)
            z.writestr('validation_report.json',json.dumps(report,indent=2))
            z.writestr('provenance_manifest.json',json.dumps(meta,indent=2))
            z.writestr('README.txt','LOCAL DRAFT ONLY. Not CCDI curator approval, certification, or data submission.\n')
        return out.getvalue()
    finally: wb.close()
