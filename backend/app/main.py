import hashlib
import io
import time
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db
from .models import Dataset
from .schemas import DatasetOut
from .storage import ensure_bucket, get_s3_client

app = FastAPI(title="PedsOnco AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
    # MinIO can take a moment to initialize even after its container starts.
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
    }


@app.get("/api/datasets", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db)):
    return list(db.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all())


@app.post("/api/datasets/upload", response_model=DatasetOut)
async def upload_dataset(
    file: UploadFile = File(...),
    project_name: str = Form("Default Project"),
    db: Session = Depends(get_db),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(Dataset).where(Dataset.sha256 == digest))
    if existing:
        return existing

    safe_name = file.filename or "upload.bin"
    object_key = f"raw/{uuid.uuid4()}/{safe_name}"

    client = get_s3_client()
    client.upload_fileobj(
        io.BytesIO(data),
        settings.s3_bucket,
        object_key,
        ExtraArgs={"ContentType": file.content_type or "application/octet-stream"},
    )

    record = Dataset(
        project_name=project_name.strip() or "Default Project",
        original_name=safe_name,
        content_type=file.content_type,
        size_bytes=len(data),
        sha256=digest,
        object_key=object_key,
        status="registered",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
