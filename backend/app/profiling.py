import csv
import gzip
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .storage import get_s3_client
from .config import settings


REFERENCE_SHEETS = {"dictionary", "terms and value sets", "readme", "instructions"}
STUDY_SHEETS = {"study", "study_admin", "study_arm", "study_funding", "study_personnel", "publication", "consent_group"}
CLINICAL_SHEETS = {
    "participant", "diagnosis", "survival", "medical_history", "treatment_response",
    "treatment_chemotherapy", "treatment_radiation", "treatment_surgery", "treatment_other",
}
BIOSPECIMEN_SHEETS = {"sample", "biospecimen", "specimen"}
FILE_SHEETS = {
    "sequencing_file", "radiology_file", "methylation_array_file", "cytogenomic_file",
    "clinical_measure_file", "pathology_file", "generic_file",
}


def classify_sheet(name: str) -> str:
    key = name.strip().lower()
    if key in REFERENCE_SHEETS or "instruction" in key or key.startswith("readme") or "dictionary" in key or "value set" in key:
        return "reference"
    if key in STUDY_SHEETS:
        return "study metadata"
    if key in CLINICAL_SHEETS:
        return "clinical"
    if key in BIOSPECIMEN_SHEETS:
        return "biospecimen"
    if key in FILE_SHEETS or key.endswith("_file"):
        return "file metadata"
    return "other"


def _read_all(object_key: str, max_bytes: int = 75 * 1024 * 1024) -> bytes:
    head = get_s3_client().head_object(Bucket=settings.s3_bucket, Key=object_key)
    size = int(head.get("ContentLength", 0))
    if size > max_bytes:
        raise ValueError(f"Structured preview is limited to {max_bytes // (1024 * 1024)} MiB; this object is {size // (1024 * 1024)} MiB.")
    response = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=object_key)
    body = response["Body"]
    try:
        return body.read(max_bytes + 1)
    finally:
        body.close()


def _sheet_preview(ws, max_rows: int = 5, max_cols: int = 12) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for idx, row in enumerate(ws.iter_rows(values_only=True)):
        if idx >= max_rows:
            break
        rows.append([value for value in row[:max_cols]])
    return rows


def _sheet_field_rows(ws, max_rows: int = 5, max_cols: int = 250) -> list[list[Any]]:
    """Read enough rows/columns to discover fields without making the UI preview huge."""
    rows: list[list[Any]] = []
    for idx, row in enumerate(ws.iter_rows(values_only=True)):
        if idx >= max_rows:
            break
        rows.append([value for value in row[:max_cols]])
    return rows



def _infer_scalar_type(values: list[Any]) -> str:
    cleaned = [value for value in values if value not in (None, "")]
    if not cleaned:
        return "unknown"
    if all(isinstance(value, bool) for value in cleaned):
        return "boolean"
    numeric = 0
    integer = 0
    for value in cleaned:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric += 1
            if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
                integer += 1
            continue
        try:
            parsed = float(str(value).strip())
            numeric += 1
            if parsed.is_integer():
                integer += 1
        except Exception:
            pass
    if numeric == len(cleaned):
        return "integer" if integer == len(cleaned) else "number"
    lowered = {str(value).strip().lower() for value in cleaned}
    if lowered and lowered <= {"true", "false", "yes", "no", "0", "1"}:
        return "boolean"
    return "string"


def _fields_from_preview(preview: list[list[Any]]) -> list[dict[str, Any]]:
    if not preview:
        return []
    headers = [str(value or "").strip() for value in preview[0]]
    fields: list[dict[str, Any]] = []
    for idx, header in enumerate(headers):
        if not header:
            continue
        samples = [row[idx] for row in preview[1:] if idx < len(row) and row[idx] not in (None, "")][:4]
        fields.append({
            "name": header,
            "inferred_type": _infer_scalar_type(samples),
            "sample_values": [str(value)[:120] for value in samples],
        })
    return fields

def profile_excel(data: bytes | str, filename: str) -> dict[str, Any]:
    wb = load_workbook(io.BytesIO(data) if isinstance(data, bytes) else data, read_only=True, data_only=True)
    sheets = []
    role_counts: dict[str, int] = {}
    try:
        for ws in wb.worksheets:
            role = classify_sheet(ws.title)
            role_counts[role] = role_counts.get(role, 0) + 1
            rows = max(int(ws.max_row or 0) - 1, 0)
            cols = int(ws.max_column or 0)
            preview = _sheet_preview(ws)
            field_rows = _sheet_field_rows(ws)
            sheets.append({
                "name": ws.title,
                "rows": rows,
                "columns": cols,
                "role": role,
                "empty": rows == 0,
                "preview": preview,
                "fields": _fields_from_preview(field_rows),
            })
    finally:
        wb.close()

    return {
        "format": "excel_workbook",
        "filename": filename,
        "table_count": len(sheets),
        "sheets": sheets,
        "role_counts": role_counts,
        "message": "All worksheets are preserved as linked tables within one cohort/study container.",
    }


def profile_delimited(data: bytes, filename: str, delimiter: str) -> dict[str, Any]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    preview = []
    field_rows = []
    row_count = 0
    max_columns = 0
    for row in reader:
        row_count += 1
        max_columns = max(max_columns, len(row))
        if len(preview) < 6:
            preview.append(row[:12])
        if len(field_rows) < 6:
            field_rows.append(row[:250])
    data_rows = max(row_count - 1, 0)
    return {
        "format": "tsv" if delimiter == "\t" else "csv",
        "filename": filename,
        "table_count": 1,
        "tables": [{"name": Path(filename).stem, "rows": data_rows, "columns": max_columns, "role": "tabular", "preview": preview, "fields": _fields_from_preview(field_rows)}],
        "message": "CSV/TSV files are single-table inputs; several files can still be linked to the same cohort.",
    }


def _flatten_paths(value: Any, prefix: str = "", paths: set[str] | None = None, depth: int = 0) -> set[str]:
    paths = paths or set()
    if depth > 6:
        return paths
    if isinstance(value, dict):
        for key, child in list(value.items())[:100]:
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            _flatten_paths(child, path, paths, depth + 1)
    elif isinstance(value, list) and value:
        _flatten_paths(value[0], f"{prefix}[]" if prefix else "[]", paths, depth + 1)
    return paths


def profile_json(data: bytes, filename: str) -> dict[str, Any]:
    parsed = json.loads(data.decode("utf-8-sig", errors="strict"))
    paths = sorted(_flatten_paths(parsed))[:250]
    records = len(parsed) if isinstance(parsed, list) else 1
    return {
        "format": "json",
        "filename": filename,
        "table_count": 1,
        "records": records,
        "paths": paths,
        "message": "Nested JSON paths are retained for semantic mapping during harmonization.",
    }


# Large-object profiling uses bounded streaming and preserves honest sample statistics.
# It never loads an arbitrarily large CSV/TSV object into RAM.
MAX_SAMPLE_ROWS = 5000
MAX_WORKBOOK_DISK_BYTES = 512 * 1024 * 1024


def _stream_delimited_profile(object_key: str, filename: str, delimiter: str) -> dict[str, Any]:
    response = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=object_key)
    body = response["Body"]
    # TextIOWrapper handles UTF-8 and CSV quoted newlines across stream chunks.
    text_stream = io.TextIOWrapper(body, encoding="utf-8-sig", errors="replace", newline="")
    try:
        reader = csv.reader(text_stream, delimiter=delimiter)
        sample = []
        field_rows = []
        max_cols = 0
        for row in reader:
            max_cols = max(max_cols, len(row))
            if len(sample) < 6:
                sample.append(row[:12])
            if len(field_rows) < 6:
                field_rows.append(row[:250])
            if len(field_rows) >= 6:
                break
        # The row count is intentionally not claimed for large objects.
        return {
            "format": "tsv" if delimiter == "\t" else "csv",
            "filename": filename,
            "table_count": 1,
            "tables": [{"name": Path(filename).stem, "rows": None,
                        "columns": max_cols, "role": "tabular", "preview": sample,
                        "fields": _fields_from_preview(field_rows)}],
            "profile_mode": "bounded_stream_sample",
            "sampled_data_rows": max(0, len(field_rows) - 1),
            "row_count_complete": False,
            "message": "Large-file preview uses a bounded streaming sample. Full row count and QC have not been calculated.",
        }
    finally:
        text_stream.close()


def _stream_excel_profile(object_key: str, filename: str, size: int) -> dict[str, Any]:
    if size > MAX_WORKBOOK_DISK_BYTES:
        return {"format": "excel_workbook", "filename": filename, "table_count": 0,
                "profile_mode": "metadata_only", "object_bytes": size,
                "message": "Workbook exceeds the 512 MiB temporary-disk profiling limit. Split it or inspect its metadata separately."}
    tmp_path = None
    response = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=object_key)
    body = response["Body"]
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
            while True:
                chunk = body.read(4 * 1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
        result = profile_excel(tmp_path, filename)
        result["profile_mode"] = "read_only_disk_spooled"
        result["object_bytes"] = size
        return result
    finally:
        body.close()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _compressed_text_preview(object_key: str, filename: str) -> dict[str, Any]:
    """Read at most 1 MiB decompressed from a GEO compressed text matrix.

    Never fully decompress an untrusted archive or claim complete row counts.
    """
    resp=get_s3_client().get_object(Bucket=settings.s3_bucket, Key=object_key)
    body=resp['Body']
    try:
        with gzip.GzipFile(fileobj=body,mode='rb') as gz:
            chunk=gz.read(1024*1024)
        underlying=filename[:-3]
        delim=',' if underlying.lower().endswith('.csv') else '\t'
        result=profile_delimited(chunk,underlying,delim)
        result['filename']=filename
        result['profile_mode']='bounded_gzip_decompressed_preview'
        result['row_count_complete']=False
        result['sampled_data_rows']=result['tables'][0]['rows']
        result['tables'][0]['rows']=None
        result['message']='Preview of at most 1 MiB uncompressed content. Counts and missingness are sampled, not full-file QC. GEO Series Matrix header lines may need a specialized parser.'
        return result
    finally:
        body.close()


def profile_dataset(object_key: str, filename: str) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    head = get_s3_client().head_object(Bucket=settings.s3_bucket, Key=object_key)
    size = int(head.get("ContentLength", 0))
    if filename.lower().endswith((".csv.gz", ".tsv.gz", ".txt.gz")):
        return _compressed_text_preview(object_key, filename)
    if suffix in {".xlsx", ".xlsm"}:
        return (profile_excel(_read_all(object_key), filename) if size <= 75 * 1024 * 1024
                else _stream_excel_profile(object_key, filename, size))
    if suffix in {".csv", ".tsv", ".txt"}:
        delimiter = "," if suffix == ".csv" else "\t"
        return (profile_delimited(_read_all(object_key), filename, delimiter)
                if size <= 75 * 1024 * 1024 else _stream_delimited_profile(object_key, filename, delimiter))
    if suffix in {".json", ".ndjson"}:
        if size <= 75 * 1024 * 1024:
            return profile_json(_read_all(object_key), filename)
        return {"format": suffix.lstrip("."), "filename": filename,
                "table_count": 0, "profile_mode": "metadata_only", "object_bytes": size,
                "message": "Large JSON is registered safely but not fully previewed; use NDJSON streaming or smaller batches for field profiling."}
    return {"format": suffix.lstrip(".") or "unknown", "filename": filename,
            "table_count": 0, "object_bytes": size,
            "message": "File is registered with the cohort; no structured preview is supported for this format."}
