# PedsOnco AI Starter

A runnable foundation for the proposed PedsOnco AI web platform.

## Architecture

- **Nginx**: web server and reverse proxy
- **React + TypeScript + Vite**: interactive frontend
- **Python + FastAPI**: API and scientific backend
- **PostgreSQL**: application and metadata database
- **MinIO**: local S3-compatible object storage
- **Docker Compose**: local multi-container deployment

This starter implements a small end-to-end vertical slice:

1. React loads through Nginx.
2. React checks `/api/health`.
3. A user uploads a file.
4. FastAPI computes SHA-256 and stores the original bytes in MinIO.
5. FastAPI stores file metadata/provenance in PostgreSQL.
6. The frontend lists registered datasets.

It intentionally does **not** yet implement the full clinical harmonization/AI pipeline.

## 1. Prerequisites

Install:

- Git
- Docker Desktop (includes Docker Compose on Mac/Windows; also available on Linux)
- Optional for non-Docker development: Python 3.12+ and Node.js 22+

Verify:

```bash
git --version
docker --version
docker compose version
node --version
python --version
```

## 2. Clone your Git repository

After creating an empty repository on GitHub/GitLab:

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_FOLDER>
```

Copy this starter's contents into that folder. Do **not** copy its parent folder as a nested repo unless that is what you want.

Then:

```bash
git add .
git status
git commit -m "Initialize PedsOnco AI web platform"
git branch -M main
git push -u origin main
```

Commit source and configuration templates. Do not commit `.env`, secrets, `node_modules`, `.venv`, raw patient data, FASTQ/BAM/CRAM/DICOM files, or generated object-storage/database volumes.

## 3. Configure environment

```bash
cp .env.example .env
```

Change the PostgreSQL and MinIO passwords in `.env` before any shared or remote deployment.

## 4. Start everything with Docker

```bash
docker compose config
docker compose up --build -d
```

Open:

- Web app: http://localhost:8080
- FastAPI Swagger docs: http://localhost:8080/docs
- MinIO Console: http://localhost:9001

View service state:

```bash
docker compose ps
```

Follow logs:

```bash
docker compose logs -f
```

Backend only:

```bash
docker compose logs -f backend
```

## 5. First test

Create a small CSV file, e.g. `demo.csv`:

```csv
participant_id,diagnosis,age_at_diagnosis
P001,Neuroblastoma,7
P002,Sarcoma,14
```

Open the web app, upload `demo.csv`, and confirm it appears in the data registry.

The file itself is stored in MinIO and its metadata is stored in PostgreSQL.

## 6. Useful Docker commands

Stop services without deleting data:

```bash
docker compose stop
```

Start again:

```bash
docker compose start
```

Rebuild after code/config changes:

```bash
docker compose up --build -d
```

Stop and remove containers/network but keep named volumes:

```bash
docker compose down
```

Delete everything including local database/object-storage volumes (**destructive**):

```bash
docker compose down -v
```

## 7. Local frontend development (optional)

Run PostgreSQL/MinIO/backend in Docker:

```bash
docker compose up -d postgres minio backend
```

Then:

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000/api npm run dev
```

Open http://localhost:5173.

## 8. Local backend development (optional)

If running FastAPI outside Docker, make a Python environment and point `DATABASE_URL` and `S3_ENDPOINT_URL` at localhost equivalents.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
fastapi dev app/main.py
```

You will normally keep PostgreSQL and MinIO running in Docker.

## 9. Git workflow

Use short feature branches rather than editing `main` directly:

```bash
git checkout -b feature/harmonization-ui
# edit files
git add .
git commit -m "Add harmonization review interface"
git push -u origin feature/harmonization-ui
```

Suggested branches/milestones:

- `feature/data-profiling`
- `feature/json-adapter`
- `feature/ccdi-schema`
- `feature/harmonization-engine`
- `feature/qc-dashboard`
- `feature/cohort-builder`
- `feature/modeling`
- `feature/export-center`

## 10. What comes next

Recommended implementation order:

1. Dataset registry and upload (this starter)
2. CSV/Excel/JSON profiler
3. Canonical CCDI/C3DC metadata model
4. AI-assisted field mapping + reviewer UI
5. QC dashboard
6. Participant → specimen → assay → file explorer
7. Cohort builder
8. Modeling + survival analysis + explainability
9. VCF/MAF adapter
10. Large-file direct-to-S3/MinIO uploads and background processing
11. Reproducibility/export center
12. Authentication, authorization, audit trail, HTTPS and deployment hardening

## Security note

This is a development starter, not a production clinical-data environment. Do not upload PHI or controlled-access human-subject data to a public or unmanaged deployment. Add authentication/authorization, encryption, audit logging, secrets management, TLS, access controls, backups and institutional compliance review before handling restricted data.
