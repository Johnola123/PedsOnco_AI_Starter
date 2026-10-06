import hashlib
import io
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
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db
from .models import Dataset, DatasetSource
from .schemas import (
    CompleteUploadRequest,
    DatasetOut,
    PresignRequest,
    PresignResponse,
    UrlImportRequest,
)
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
    version="0.3.0",
    description=(
        "Dataset registry and object-storage gateway for browser-direct presigned uploads, "
        "URL/API imports, and cohort-aware file registration."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
