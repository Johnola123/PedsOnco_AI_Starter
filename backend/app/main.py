import hashlib
import io
import json
import ipaddress
import os
import socket
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db
from .models import CohortMerge, CohortWorkspaceRecord, Dataset, DatasetProfile, DatasetSource
from .schemas import (
    CohortMergeOut,
    CohortMergeRequest,
    CohortSummary,
    CompleteUploadRequest,
    DatasetOut,
    DatasetProfileOut,
    PresignRequest,
    PresignResponse,
    UrlImportRequest,
    WorkspaceRecordOut,
    WorkspaceRecordRequest,
    HarmonizationValidationRequest,
    HarmonizationValidationOut,
    IntegrationValidationRequest,
    IntegrationValidationOut,
    ValidationIssue,
)
from .profiling import profile_dataset
from .storage import (
    delete_object,
    ensure_bucket,
    generate_download_url,
    generate_upload_url,
    get_s3_client,
    object_head,
    sha256_for_object,
)

app = FastAPI(
    title="PedsOnco AI API",
    version="1.3.0",
    description=(
        "Dataset registry and object-storage gateway for browser-direct presigned uploads, "
        "URL/API imports, multi-sheet workbook inspection, cohort-aware file registration, and logical cohort merging."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


CANONICAL_FIELDS = {
    "participant_id", "sample_id", "diagnosis", "age_at_diagnosis", "sex", "race", "ethnicity",
    "vital_status", "days_to_death", "treatment_response", "file_name", "library_id",
    "study_id", "study_name", "consent_group", "treatment_type", "treatment_start_day",
    "treatment_end_day", "event_free_survival_days", "event_free_survival_status", "tumor_site",
    "histology", "stage", "molecular_subtype", "specimen_type", "collection_age_days",
}


def _profile_payload(dataset: Dataset, db: Session) -> dict:
    cached = db.scalar(select(DatasetProfile).where(DatasetProfile.dataset_id == dataset.id))
    if cached:
        try:
            return json.loads(cached.profile_json)
        except Exception:
            pass
    result = profile_dataset(dataset.object_key, dataset.original_name)
    if cached:
        cached.format_name = result.get("format", "unknown")
        cached.table_count = int(result.get("table_count", 0))
        cached.profile_json = json.dumps(result, default=str)
    else:
        db.add(DatasetProfile(
            dataset_id=dataset.id,
            format_name=result.get("format", "unknown"),
            table_count=int(result.get("table_count", 0)),
            profile_json=json.dumps(result, default=str),
        ))
    db.commit()
    return result


def _profile_fields(profile: dict, table_name: str | None = None) -> set[str]:
    if profile.get("paths"):
        return {str(path) for path in profile.get("paths", [])}
    items = list(profile.get("sheets", [])) + list(profile.get("tables", []))
    if table_name:
        selected = next((item for item in items if str(item.get("name")) == table_name), None)
        items = [selected] if selected else []
    fields: set[str] = set()
    for item in items:
        if not item:
            continue
        for field in item.get("fields", []):
            name = str(field.get("name", "")).strip()
            if name:
                fields.add(name)
        if not item.get("fields") and item.get("preview"):
            for value in item.get("preview", [[]])[0]:
                name = str(value or "").strip()
                if name:
                    fields.add(name)
    return fields


def wait_for_database(attempts: int = 20, delay: float = 2.0) -> None:
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError:
            if attempt == attempts:
                raise
            time.sleep(delay)


@app.on_event("startup")
def startup() -> None:
    wait_for_database()
    Base.metadata.create_all(bind=engine)
    for attempt in range(1, 16):
        try:
            ensure_bucket()
            break
        except Exception:
            if attempt == 15:
                raise
            time.sleep(2)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "connected",
        "object_storage": settings.s3_bucket,
        "direct_uploads": True,
        "url_imports": True,
    }


@app.get("/api/datasets", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db)):
    return list(db.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all())


def safe_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        return "upload.bin"
    # Avoid control characters and awkward path-like names while preserving useful extensions.
    return "".join(ch for ch in name if ch.isprintable() and ch not in {"/", "\\"})[:500] or "upload.bin"


def new_object_key(filename: str) -> str:
    return f"raw/{uuid.uuid4()}/{safe_filename(filename)}"


def register_dataset(
    *,
    db: Session,
    project_name: str,
    filename: str,
    content_type: str | None,
    size_bytes: int,
    sha256: str,
    object_key: str,
    source_type: str,
    source_url: str | None = None,
) -> Dataset:
    existing = db.scalar(select(Dataset).where(Dataset.sha256 == sha256))
    if existing:
        if existing.object_key != object_key:
            try:
                delete_object(object_key)
            except Exception:
                pass
        return existing

    record = Dataset(
        project_name=project_name.strip() or "Default Project",
        original_name=safe_filename(filename),
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        object_key=object_key,
        status="registered",
    )
    record.source = DatasetSource(source_type=source_type, source_url=source_url)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# Browser/API direct-to-object-storage flow
# 1) request presigned URL
# 2) browser/API client PUTs bytes directly to MinIO/S3
# 3) client calls complete endpoint; FastAPI verifies object + registers metadata
# ---------------------------------------------------------------------------
@app.post("/api/uploads/presign", response_model=PresignResponse)
def presign_upload(payload: PresignRequest):
    filename = safe_filename(payload.filename)
    content_type = payload.content_type or "application/octet-stream"
    object_key = new_object_key(filename)
    return PresignResponse(
        object_key=object_key,
        upload_url=generate_upload_url(object_key, content_type),
        headers={"Content-Type": content_type},
        expires_in=settings.presign_expires_seconds,
    )


@app.post("/api/uploads/complete", response_model=DatasetOut)
def complete_upload(payload: CompleteUploadRequest, db: Session = Depends(get_db)):
    if not payload.object_key.startswith("raw/"):
        raise HTTPException(status_code=400, detail="Invalid object key.")

    try:
        head = object_head(payload.object_key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Uploaded object was not found in object storage.") from exc

    size_bytes = int(head.get("ContentLength", 0))
    if size_bytes <= 0:
        raise HTTPException(status_code=400, detail="Uploaded object is empty.")

    # Hash after upload so even multi-GB browser uploads do not need to be buffered in FastAPI.
    digest = sha256_for_object(payload.object_key)

    return register_dataset(
        db=db,
        project_name=payload.project_name,
        filename=payload.filename,
        content_type=head.get("ContentType") or payload.content_type,
        size_bytes=size_bytes,
        sha256=digest,
        object_key=payload.object_key,
        source_type="browser_direct",
    )


@app.get("/api/datasets/{dataset_id}/download-url")
def dataset_download_url(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return {
        "dataset_id": dataset.id,
        "url": generate_download_url(dataset.object_key),
        "expires_in": settings.presign_expires_seconds,
    }


# ---------------------------------------------------------------------------
# External URL/API import
# Server-side import is used because arbitrary external sites often block browser
# cross-origin reads. Authorization is transient and is never stored.
# ---------------------------------------------------------------------------
def _validate_public_http_url(raw_url: str) -> None:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only http:// and https:// URLs are supported.")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL must include a hostname.")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="Could not resolve the external hostname.") from exc

    for info in addresses:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise HTTPException(status_code=400, detail="Private or local network URLs are not allowed.")


def _filename_from_response(requested: str | None, response: httpx.Response, source_url: str) -> str:
    if requested:
        return safe_filename(requested)

    disposition = response.headers.get("content-disposition", "")
    marker = "filename="
    if marker in disposition.lower():
        value = disposition.split("=", 1)[1].strip().strip('"\'')
        if value:
            return safe_filename(unquote(value))

    path_name = Path(unquote(urlparse(source_url).path)).name
    if path_name:
        return safe_filename(path_name)

    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
    suffix = {
        "application/json": ".json",
        "text/csv": ".csv",
        "text/tab-separated-values": ".tsv",
        "application/zip": ".zip",
    }.get(content_type, ".bin")
    return f"external_import{suffix}"


def _stream_external_to_tempfile(url: str, bearer_token: str | None):
    headers = {"User-Agent": "PedsOnco-AI/0.3"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    current_url = url
    max_redirects = 5
    temp = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024, mode="w+b")
    digest = hashlib.sha256()
    total = 0

    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=20.0), follow_redirects=False) as client:
            for redirect_count in range(max_redirects + 1):
                _validate_public_http_url(current_url)
                with client.stream("GET", current_url, headers=headers) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        if redirect_count == max_redirects:
                            raise HTTPException(status_code=400, detail="Too many redirects from external source.")
                        location = response.headers.get("location")
                        if not location:
                            raise HTTPException(status_code=400, detail="Redirect did not include a location.")
                        next_url = str(httpx.URL(current_url).join(location))
                        if bearer_token:
                            current_host = (urlparse(current_url).hostname or "").lower()
                            next_host = (urlparse(next_url).hostname or "").lower()
                            if current_host != next_host:
                                raise HTTPException(
                                    status_code=400,
                                    detail="Authenticated imports cannot redirect to a different hostname.",
                                )
                        current_url = next_url
                        continue

                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise HTTPException(
                            status_code=400,
                            detail=f"External source returned HTTP {response.status_code}.",
                        ) from exc

                    declared = response.headers.get("content-length")
                    if declared and int(declared) > settings.max_url_import_bytes:
                        raise HTTPException(status_code=413, detail="External object exceeds the configured import size limit.")

                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > settings.max_url_import_bytes:
                            raise HTTPException(status_code=413, detail="External object exceeds the configured import size limit.")
                        digest.update(chunk)
                        temp.write(chunk)

                    temp.seek(0)
                    return temp, digest.hexdigest(), total, response, current_url

            raise HTTPException(status_code=400, detail="External import failed.")
    except Exception:
        temp.close()
        raise


@app.post("/api/import/url", response_model=DatasetOut)
def import_from_url(payload: UrlImportRequest, db: Session = Depends(get_db)):
    source_url = str(payload.url)
    temp, digest, total, response, final_url = _stream_external_to_tempfile(source_url, payload.bearer_token)
    try:
        existing = db.scalar(select(Dataset).where(Dataset.sha256 == digest))
        if existing:
            return existing

        filename = _filename_from_response(payload.filename, response, final_url)
        object_key = new_object_key(filename)
        content_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0]

        get_s3_client().upload_fileobj(
            temp,
            settings.s3_bucket,
            object_key,
            ExtraArgs={
                "ContentType": content_type,
                "Metadata": {"source": "external-url"},
            },
        )

        source_type = "api" if payload.bearer_token else "url"
        parsed_source = urlparse(source_url)
        stored_source_url = parsed_source._replace(query="", fragment="").geturl()
        return register_dataset(
            db=db,
            project_name=payload.project_name,
            filename=filename,
            content_type=content_type,
            size_bytes=total,
            sha256=digest,
            object_key=object_key,
            source_type=source_type,
            source_url=stored_source_url,
        )
    finally:
        temp.close()


# Legacy fallback for small files. The React app no longer uses this path; it is
# kept for CLI/testing and environments where direct object-storage access is not available.
@app.post("/api/datasets/upload", response_model=DatasetOut)
async def upload_dataset_legacy(
    file: UploadFile = File(...),
    project_name: str = Form("Default Project"),
    db: Session = Depends(get_db),
):
    digest = hashlib.sha256()
    total = 0
    temp = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024, mode="w+b")
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
            temp.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        sha = digest.hexdigest()
        existing = db.scalar(select(Dataset).where(Dataset.sha256 == sha))
        if existing:
            return existing

        filename = safe_filename(file.filename or "upload.bin")
        object_key = new_object_key(filename)
        temp.seek(0)
        get_s3_client().upload_fileobj(
            temp,
            settings.s3_bucket,
            object_key,
            ExtraArgs={"ContentType": file.content_type or "application/octet-stream"},
        )
        return register_dataset(
            db=db,
            project_name=project_name,
            filename=filename,
            content_type=file.content_type,
            size_bytes=total,
            sha256=sha,
            object_key=object_key,
            source_type="api_multipart",
        )
    finally:
        temp.close()


# ---------------------------------------------------------------------------
# Cohort workspace + structured-file inspection
# A cohort is represented by project_name so existing uploads remain compatible.
# Merged cohorts are logical views: raw source files are never duplicated or rewritten.
# ---------------------------------------------------------------------------
def _file_format(name: str) -> str:
    lower = name.lower()
    compound = [".fastq.gz", ".fq.gz", ".vcf.gz", ".fasta.gz", ".fa.gz"]
    for suffix in compound:
        if lower.endswith(suffix):
            return suffix.lstrip(".")
    return Path(name).suffix.lower().lstrip(".") or "file"


def _source_cohort_names(db: Session) -> list[str]:
    rows = db.execute(select(Dataset.project_name).distinct().order_by(Dataset.project_name)).all()
    return [row[0] for row in rows if row[0]]


def _merge_sources(merge: CohortMerge) -> list[str]:
    try:
        value = json.loads(merge.source_cohorts_json)
        return [str(item) for item in value]
    except Exception:
        return []


@app.get("/api/cohorts", response_model=list[CohortSummary])
def list_cohorts(db: Session = Depends(get_db)):
    source_names = _source_cohort_names(db)
    results: list[CohortSummary] = []
    for name in source_names:
        files = list(db.scalars(select(Dataset).where(Dataset.project_name == name)).all())
        results.append(
            CohortSummary(
                name=name,
                kind="source",
                file_count=len(files),
                size_bytes=sum(item.size_bytes for item in files),
                formats=sorted({_file_format(item.original_name) for item in files}),
                source_cohorts=[],
            )
        )

    for merge in db.scalars(select(CohortMerge).order_by(CohortMerge.created_at.desc())).all():
        sources = _merge_sources(merge)
        files = list(db.scalars(select(Dataset).where(Dataset.project_name.in_(sources))).all()) if sources else []
        results.append(
            CohortSummary(
                name=merge.name,
                kind="merged",
                file_count=len(files),
                size_bytes=sum(item.size_bytes for item in files),
                formats=sorted({_file_format(item.original_name) for item in files}),
                source_cohorts=sources,
            )
        )
    return results


@app.get("/api/cohorts/{cohort_name}/datasets", response_model=list[DatasetOut])
def cohort_datasets(cohort_name: str, db: Session = Depends(get_db)):
    merge = db.scalar(select(CohortMerge).where(CohortMerge.name == cohort_name))
    if merge:
        sources = _merge_sources(merge)
        return list(db.scalars(select(Dataset).where(Dataset.project_name.in_(sources)).order_by(Dataset.created_at.desc())).all())
    return list(db.scalars(select(Dataset).where(Dataset.project_name == cohort_name).order_by(Dataset.created_at.desc())).all())


@app.post("/api/cohorts/merge", response_model=CohortMergeOut)
def merge_cohorts(payload: CohortMergeRequest, db: Session = Depends(get_db)):
    name = payload.name.strip()
    sources = list(dict.fromkeys(item.strip() for item in payload.source_cohorts if item.strip()))
    if len(sources) < 2:
        raise HTTPException(status_code=400, detail="Choose at least two distinct source cohorts.")
    available = set(_source_cohort_names(db))
    missing = [item for item in sources if item not in available]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown source cohort(s): {', '.join(missing)}")
    if name in available:
        raise HTTPException(status_code=409, detail="A source cohort already uses this name.")
    existing = db.scalar(select(CohortMerge).where(CohortMerge.name == name))
    if existing:
        raise HTTPException(status_code=409, detail="A merged cohort already uses this name.")

    record = CohortMerge(
        name=name,
        source_cohorts_json=json.dumps(sources),
        notes=payload.notes,
        status="logical_merge",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return CohortMergeOut(
        id=record.id,
        name=record.name,
        source_cohorts=sources,
        notes=record.notes,
        status=record.status,
        created_at=record.created_at,
    )


@app.get("/api/cohort-merges", response_model=list[CohortMergeOut])
def cohort_merges(db: Session = Depends(get_db)):
    output = []
    for record in db.scalars(select(CohortMerge).order_by(CohortMerge.created_at.desc())).all():
        output.append(
            CohortMergeOut(
                id=record.id,
                name=record.name,
                source_cohorts=_merge_sources(record),
                notes=record.notes,
                status=record.status,
                created_at=record.created_at,
            )
        )
    return output


@app.get("/api/datasets/{dataset_id}/profile", response_model=DatasetProfileOut)
def dataset_profile(dataset_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    cached = db.scalar(select(DatasetProfile).where(DatasetProfile.dataset_id == dataset_id))
    if cached and not refresh:
        return DatasetProfileOut(
            dataset_id=dataset.id,
            format_name=cached.format_name,
            table_count=cached.table_count,
            profile=json.loads(cached.profile_json),
        )

    try:
        result = profile_dataset(dataset.object_key, dataset.original_name)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not inspect this file: {exc}") from exc

    format_name = str(result.get("format", "unknown"))
    table_count = int(result.get("table_count", 0))
    if cached:
        cached.format_name = format_name
        cached.table_count = table_count
        cached.profile_json = json.dumps(result, default=str)
    else:
        cached = DatasetProfile(
            dataset_id=dataset.id,
            format_name=format_name,
            table_count=table_count,
            profile_json=json.dumps(result, default=str),
        )
        db.add(cached)
    db.commit()
    return DatasetProfileOut(dataset_id=dataset.id, format_name=format_name, table_count=table_count, profile=result)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Human-in-the-loop validation
# ---------------------------------------------------------------------------

@app.post("/api/harmonization/validate", response_model=HarmonizationValidationOut)
def validate_harmonization(payload: HarmonizationValidationRequest, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, payload.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    profile = _profile_payload(dataset, db)
    source_fields = _profile_fields(profile, payload.table_name)
    issues: list[ValidationIssue] = []
    accepted = [item for item in payload.mappings if item.status == "accept"]
    reviewed = [item for item in payload.mappings if item.status == "review"]
    rejected = [item for item in payload.mappings if item.status == "reject"]

    canonical_seen: dict[str, list[str]] = {}
    for item in payload.mappings:
        if item.source not in source_fields:
            issues.append(ValidationIssue(level="error", code="SOURCE_NOT_FOUND", field=item.source, message="Source field is not present in the selected table/profile."))
        if item.status == "accept" and not item.canonical.strip():
            issues.append(ValidationIssue(level="error", code="EMPTY_CANONICAL", field=item.source, message="Accepted mappings require a canonical target."))
        if item.status != "reject" and item.canonical:
            canonical_seen.setdefault(item.canonical.strip(), []).append(item.source)
            if item.canonical.strip() not in CANONICAL_FIELDS:
                issues.append(ValidationIssue(level="warning", code="CUSTOM_CANONICAL", field=item.source, message=f"'{item.canonical}' is not in the Milestone 1 canonical field catalog; it will be preserved as a custom target."))
        if item.status == "accept" and item.confidence < 70:
            issues.append(ValidationIssue(level="warning", code="LOW_CONFIDENCE_ACCEPTED", field=item.source, message="Low-confidence proposal was accepted; manual review is recommended."))

    for canonical, sources in canonical_seen.items():
        if len(sources) > 1:
            issues.append(ValidationIssue(level="warning", code="DUPLICATE_TARGET", field=canonical, message=f"Multiple source fields map to '{canonical}': {', '.join(sources)}."))

    if reviewed:
        issues.append(ValidationIssue(level="warning", code="REVIEW_PENDING", message=f"{len(reviewed)} mapping(s) are still marked Review."))
    if not accepted:
        issues.append(ValidationIssue(level="error", code="NO_ACCEPTED_MAPPINGS", message="At least one mapping must be accepted before confirmation."))

    errors = [issue for issue in issues if issue.level == "error"]
    score = max(0, min(100, round((len(accepted) / max(1, len(payload.mappings))) * 100 - len(errors) * 15 - len(reviewed) * 3)))
    return HarmonizationValidationOut(
        valid=not errors, dataset_id=dataset.id, dataset_name=dataset.original_name, table_name=payload.table_name,
        score=score, accepted_count=len(accepted), review_count=len(reviewed), rejected_count=len(rejected), issues=issues,
    )


@app.post("/api/integration/validate", response_model=IntegrationValidationOut)
def validate_integration(payload: IntegrationValidationRequest, db: Session = Depends(get_db)):
    left = db.get(Dataset, payload.left_dataset_id)
    right = db.get(Dataset, payload.right_dataset_id)
    if not left or not right:
        raise HTTPException(status_code=404, detail="One or both datasets were not found.")
    issues: list[ValidationIssue] = []
    if left.id == right.id:
        issues.append(ValidationIssue(level="error", code="SAME_DATASET", message="Choose two different datasets for integration."))
    left_fields = _profile_fields(_profile_payload(left, db))
    right_fields = _profile_fields(_profile_payload(right, db))
    if payload.left_key not in left_fields:
        issues.append(ValidationIssue(level="error", code="LEFT_KEY_NOT_FOUND", field=payload.left_key, message="Left join key is not present in the profiled source."))
    if payload.right_key not in right_fields:
        issues.append(ValidationIssue(level="error", code="RIGHT_KEY_NOT_FOUND", field=payload.right_key, message="Right join key is not present in the profiled source."))
    if payload.left_key != payload.right_key:
        issues.append(ValidationIssue(level="warning", code="DIFFERENT_KEY_NAMES", message="Join keys use different names; confirm they represent the same entity."))
    return IntegrationValidationOut(valid=not any(issue.level == "error" for issue in issues), left_dataset_name=left.original_name, right_dataset_name=right.original_name, issues=issues)


# Cohort workspace records
# Persist human-reviewed harmonization mappings, edit recipes, integration
# relationships, and other non-destructive workspace decisions. Raw data are
# never overwritten by these operations.
# ---------------------------------------------------------------------------

def _workspace_out(record: CohortWorkspaceRecord) -> WorkspaceRecordOut:
    try:
        payload = json.loads(record.payload_json)
    except Exception:
        payload = {}
    return WorkspaceRecordOut(
        id=record.id,
        project_name=record.project_name,
        record_type=record.record_type,
        name=record.name,
        payload=payload,
        created_at=record.created_at,
    )


@app.get("/api/cohorts/{cohort_name}/workspace-records", response_model=list[WorkspaceRecordOut])
def list_workspace_records(cohort_name: str, record_type: str | None = None, db: Session = Depends(get_db)):
    statement = select(CohortWorkspaceRecord).where(CohortWorkspaceRecord.project_name == cohort_name)
    if record_type:
        statement = statement.where(CohortWorkspaceRecord.record_type == record_type)
    records = db.scalars(statement.order_by(CohortWorkspaceRecord.created_at.desc())).all()
    return [_workspace_out(record) for record in records]


@app.post("/api/cohorts/{cohort_name}/workspace-records", response_model=WorkspaceRecordOut)
def create_workspace_record(cohort_name: str, payload: WorkspaceRecordRequest, db: Session = Depends(get_db)):
    record = CohortWorkspaceRecord(
        project_name=cohort_name,
        record_type=payload.record_type.strip().lower(),
        name=payload.name.strip(),
        payload_json=json.dumps(payload.payload, default=str),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _workspace_out(record)


@app.delete("/api/cohorts/{cohort_name}/workspace-records/{record_id}")
def delete_workspace_record(cohort_name: str, record_id: int, db: Session = Depends(get_db)):
    record = db.get(CohortWorkspaceRecord, record_id)
    if not record or record.project_name != cohort_name:
        raise HTTPException(status_code=404, detail="Workspace record not found.")
    db.delete(record)
    db.commit()
    return {"status": "deleted", "id": record_id}


@app.get("/api/cohorts/{cohort_name}/export-manifest")
def cohort_export_manifest(cohort_name: str, db: Session = Depends(get_db)):
    files = cohort_datasets(cohort_name, db)
    records = list_workspace_records(cohort_name, None, db)
    return {
        "cohort": cohort_name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": [DatasetOut.model_validate(item).model_dump(mode="json") for item in files],
        "workspace_records": [record.model_dump(mode="json") for record in records],
        "provenance_note": "Raw source objects are preserved; workspace records describe harmonization, edits, and integrations non-destructively.",
    }
