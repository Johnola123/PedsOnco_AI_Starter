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


def inspect_workbook(data: bytes, *, check_values: bool = False) -> dict[str, Any]:
    if len(data) > 20 * 1024 * 1024:
        raise ValueError('Workbook is larger than 20 MiB; use a smaller CCDI metadata workbook.')
    wb = load_workbook(io.BytesIO(data), read_only=False, data_only=True)
    try:
        result = {'sheets': [], 'issues': [], 'required_nodes': list(REQUIRED_NODES),
                  'template_sha256': hashlib.sha256(data).hexdigest(),
                  'mode': 'populated-workbook-check' if check_values else 'template-inspection',
                  'validated_against_live_ccdi': False}
        available = {ws.title.strip().lower(): ws.title for ws in wb.worksheets}
        for node in REQUIRED_NODES:
            if node not in available:
                result['issues'].append({'level': 'error', 'code': 'MISSING_REQUIRED_SHEET', 'sheet': node,
                                         'message': f'Missing CCDI standard node sheet {node}.'})
        for ws in wb.worksheets:
            if _is_reference(ws.title):
                continue
            row_index, headers, warnings = _headers(ws)
            columns = [{'name': name, 'column': i + 1} for i, name in enumerate(headers) if name]
            for warning in warnings:
                result['issues'].append({'level': 'warning', 'code': 'HEADER_REVIEW', 'sheet': ws.title, 'message': warning})
            populated = 0
            if row_index:
                for row in ws.iter_rows(min_row=row_index + 1, max_row=min(ws.max_row, row_index + 10001), values_only=True):
                    if any(value is not None and str(value).strip() for value in row):
                        populated += 1
                if ws.max_row > row_index + 10001:
                    result['issues'].append({'level':'warning','code':'ROW_LIMIT','sheet':ws.title,
                                             'message':'Checked only the first 10,001 data rows.'})
            result['sheets'].append({'name': ws.title, 'header_row': row_index, 'fields': columns, 'nonempty_rows': populated})
            if check_values and ws.title.strip().lower() in REQUIRED_NODES and populated == 0:
                result['issues'].append({'level': 'warning', 'code': 'REQUIRED_SHEET_EMPTY', 'sheet': ws.title,
                                         'message': 'Required study-level or participant-level sheet has no populated rows.'})
            # Yellow highlighting differs by template release; do not infer missing required properties from fill alone.
        result['summary'] = {'sheet_count': len(result['sheets']),
                             'error_count': sum(i['level'] == 'error' for i in result['issues']),
                             'warning_count': sum(i['level'] == 'warning' for i in result['issues'])}
        result['status'] = 'structural-errors' if result['summary']['error_count'] else 'preliminary-review-required'
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
        if any(v not in indices for v in mappings.values()):
            raise ValueError('At least one mapping target is absent in CCDI node headers.')
        if len(set(mappings.values())) != len(mappings):
            raise ValueError('Multiple source fields target the same CCDI property.')
        # Avoid accidentally altering template content: refuse to overwrite existing populated node rows.
        for row in target.iter_rows(min_row=hdr_idx + 1, values_only=True):
            if any(v is not None and str(v).strip() for v in row):
                raise ValueError('The target sheet already has data; choose a blank official CCDI template.')
        for ridx, record in enumerate(records, start=hdr_idx + 1):
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
