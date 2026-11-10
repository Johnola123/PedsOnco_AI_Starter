"""Conservative metadata-only modality recognition for cached profiles.

Never infer clinical outcomes, unique patients, image quality, or gene counts from filenames.
"""
import re
from collections import Counter
from pathlib import Path

EXPRESSION = {'gene', 'gene_id', 'gene_name', 'ensembl_id', 'gene_symbol', 'symbol', 'expression', 'tpm', 'fpkm', 'counts', 'read_count', 'normalized_count', 'log2fc', 'log2foldchange', 'transcript_id', 'feature_id'}
CLINICAL = {'diagnosis', 'primary_diagnosis', 'age', 'age_at_diagnosis', 'sex', 'gender', 'stage', 'tumor_stage', 'vital_status', 'survival', 'days_to_death', 'days_to_last_follow_up', 'treatment', 'treatment_response', 'histology', 'disease_type', 'disease_status'}
IDENTIFIERS = {'participant_id', 'patient_id', 'case_id', 'sample_id', 'specimen_id', 'biospecimen_id', 'submitter_id', 'aliquot_id', 'gsm', 'geo_accession', 'library_id', 'subject_id'}
IMAGING = {'modality', 'series_instance_uid', 'study_instance_uid', 'sop_instance_uid', 'pixel_spacing', 'slice_thickness', 'image_width', 'image_height', 'rows', 'columns', 'manufacturer', 'body_part_examined', 'collection', 'series_uid', 'image_type'}
IMAGE_EXT = ('.dcm', '.dicom', '.nii', '.nii.gz', '.nrrd', '.svs', '.ndpi', '.tiff', '.tif', '.png', '.jpg', '.jpeg', '.ome.tiff')
SEQ_EXT = ('.fastq', '.fastq.gz', '.fq', '.fq.gz', '.bam', '.cram', '.vcf', '.vcf.gz', '.fasta', '.fa')

def clean(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value or '').strip().lower()).strip('_')

def classify_table(table, filename):
    """Return modality candidates with explicit evidence and uncertainty.

    Roles from the CCDI workbook help distinguish file manifests from actual images.
    """
    name = clean(table.get('name',''))
    role = clean(table.get('role',''))
    headers = {clean(f.get('name')) for f in table.get('fields',[]) if f.get('name')}
    header_groups = {
        'expression': sorted(headers & EXPRESSION),
        'clinical': sorted(headers & CLINICAL),
        'identifiers': sorted(headers & IDENTIFIERS),
        'imaging': sorted(headers & IMAGING),
    }
    scores = {k: len(v) for k,v in header_groups.items()}
    # GEO/GDC tables often encode samples as columns rather than a 'sample_id' field.
    sample_headers=[h for h in headers if re.fullmatch(r'gsm\d+|tcga_[a-z0-9_]+|sample_?\d+|srr\d+',h)]
    expression_matrix_candidate=bool((headers & {'gene','gene_id','gene_name','gene_symbol','ensembl_id'}) and len(sample_headers)>=2)
    signals=[]
    # A single ambiguous column is not enough to call a generic wide table expression.
    if scores['expression'] >= 2 or expression_matrix_candidate or (scores['expression'] >= 1 and any(t in name for t in ('rna','expression','counts','transcript'))):
        signals.append(('expression', 'header matches'))
    if scores['clinical'] >= 2 or (scores['clinical'] >= 1 and role=='clinical'):
        signals.append(('clinical', 'clinical field matches'))
    if scores['identifiers'] >= 1:
        signals.append(('identifiers', 'identifier field matches'))
    if scores['imaging'] >= 2 or ('radiology' in name or 'imaging' in name or 'pathology_file' in name):
        signals.append(('imaging_metadata', 'imaging fields or sheet name'))
    if role == 'clinical' and not any(k=='clinical' for k,_ in signals):
        signals.append(('clinical', 'CCDI sheet role'))
    if role=='biospecimen' and not any(k=='identifiers' for k,_ in signals):
        signals.append(('identifiers', 'CCDI biospecimen sheet role'))
    if role=='reference':
        return {'name':table.get('name','data'),'categories':['reference'],'evidence':['Reference worksheet'], 'field_groups':header_groups, 'sample_column_candidates':sample_headers[:30], 'expression_matrix_candidate':expression_matrix_candidate, 'rows_reported':table.get('rows'),'columns_reported':table.get('columns')}
    return {'name':table.get('name','data'),'categories':[s[0] for s in signals] or ['other_tabular'],
            'evidence':[s[1] for s in signals], 'field_groups':header_groups, 'sample_column_candidates':sample_headers[:30], 'expression_matrix_candidate':expression_matrix_candidate,
            'rows_reported':table.get('rows'), 'columns_reported':table.get('columns')}

def modality_summary(profile, filename):
    filename_lower=filename.lower()
    raw_image=filename_lower.endswith(IMAGE_EXT)
    raw_sequence=filename_lower.endswith(SEQ_EXT)
    tables=(profile or {}).get('tables',[])+(profile or {}).get('sheets',[])
    detail=[classify_table(t,filename) for t in tables]
    categories=set(k for t in detail for k in t['categories'] if k!='reference')
    if raw_image: categories.add('imaging_file')
    if raw_sequence: categories.add('sequence_file')
    # Filename alone is insufficient to claim structured expression or imaging features.
    if not categories: categories={'unclassified'}
    return {'categories':sorted(categories), 'tables':detail,
            'classification':'fields_and_sheet_roles' if tables else ('file_extension_only' if raw_image or raw_sequence else 'insufficient_metadata'),
            'cautions':([
                'Image format identified; pixel data, acquisition quality, and DICOM metadata have not been decoded.'
            ] if raw_image else [])+([
                'Sequence file format identified; biological content has not been parsed.'
            ] if raw_sequence else [])+([
                'Metadata-based categorization does not establish biological meaning or validate sample linkage.'
            ])}

def category_totals(items):
    count=Counter()
    for item in items:
        for category in item['modality']['categories']:
            count[category]+=1
    return dict(count)
