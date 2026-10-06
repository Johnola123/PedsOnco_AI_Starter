# PedsOnco AI Starter — Direct S3/MinIO Upload Edition

A deployable starter for a multimodal pediatric-oncology research web application.

## Architecture

```text
Browser / API client
        |
        | 1. POST /api/uploads/presign
        v
      FastAPI  ------------------------> PostgreSQL
        |                                  metadata registry
        | returns short-lived signed URL
        v
Browser / API client -- direct PUT --> MinIO / S3
        |
        | 2. POST /api/uploads/complete
        v
      FastAPI -- HEAD + SHA-256 --> register dataset
```

External URL/API import uses a safe server-side path:

```text
External HTTPS URL / GET API
        |
        v
      FastAPI  -- streaming --> MinIO / S3
        |
        +---------------------> PostgreSQL
```

The React app never sends large local files through Nginx/FastAPI. FastAPI signs the upload; the browser sends the file directly to object storage. This is the intended path for FASTQ, BAM/CRAM, DICOM, images, Parquet, and other large objects.

## Stack

- **Nginx** — serves the production React build and proxies `/api` to FastAPI
- **React + TypeScript + Vite** — responsive web UI
- **Python 3.12 + FastAPI** — API, presigning, URL/API import, registration
- **PostgreSQL 17** — dataset/cohort metadata
- **MinIO / S3** — original files and large objects
- **Docker Compose** — local/development deployment

## Included capabilities

- Multi-file browser uploads using presigned S3/MinIO PUT URLs
- Upload progress in the React UI
- External public URL import
- GET API import with optional Bearer token
- Bearer tokens are transient and are not written to the database
- SSRF protections block loopback/private/link-local destinations
- SHA-256 registration and duplicate detection
- Short-lived presigned download URLs
- Cohort/project grouping
- Responsive registry and upload UI
- CSV, TSV, Excel, JSON/NDJSON, FASTA/FASTQ, VCF/MAF, BAM/CRAM, images/DICOM, Parquet and generic files
- Synthetic multimodal cohort examples under `sample_data/`

## 1. Prerequisites

On macOS Apple Silicon, install Docker Desktop for Apple Silicon. Verify:

```bash
git --version
docker --version
docker compose version
```

Node/Python are optional for the Docker-only path. For local development outside Docker, Node 22+ and Python 3.12 are recommended.

## 2. Configure

From the repository root:

```bash
cp .env.example .env
```

For local testing on the **same Mac**, keep:

```env
S3_ENDPOINT_URL=http://minio:9000
S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
WEB_ORIGINS=http://localhost:8080,http://localhost:5173
```

Change the example passwords in `.env` before any shared deployment.

### Testing from a phone/tablet on your LAN

`localhost` on the phone means the phone itself. Use the Mac's reachable LAN address instead, for example:

```env
S3_PUBLIC_ENDPOINT_URL=http://192.168.1.50:9000
WEB_ORIGINS=http://192.168.1.50:8080,http://localhost:8080,http://localhost:5173
```

Open `http://192.168.1.50:8080` on the mobile device. Your firewall must allow the ports. For any real deployment, use HTTPS hostnames instead of LAN IPs.

## 3. Start the full stack

```bash
docker compose config
docker compose up --build -d
docker compose ps
```

Open:

- Web app: `http://localhost:8080`
- FastAPI Swagger docs: `http://localhost:8080/docs`
- MinIO console: `http://localhost:9001`
- MinIO S3 API: `http://localhost:9000`

View logs:

```bash
docker compose logs -f backend
docker compose logs -f web
```

Stop:

```bash
docker compose down
```

Delete development database/object-store volumes too:

```bash
docker compose down -v
```

> If upgrading from the older starter before this direct-upload edition and you only have disposable demo data, `docker compose down -v` is the simplest way to start with the current schema.

## 4. Test direct browser upload

Use the **Computer / device** tab in the web app:

1. Enter a cohort/project name.
2. Select one or more files.
3. FastAPI returns one presigned PUT URL per file.
4. The browser uploads each file directly to MinIO/S3.
5. The browser asks FastAPI to complete registration.
6. FastAPI verifies the object, calculates SHA-256 in a streaming fashion, and writes metadata to PostgreSQL.

This means large file bytes do **not** pass through Nginx or FastAPI during the initial upload.

## 5. Test external URL / API import

Use the **External URL / API** tab.

Supported MVP pattern:

- HTTP(S) public download URL, or
- HTTP(S) GET API endpoint
- optional Bearer token
- optional filename override

The server streams the response to a temporary spool, calculates SHA-256, then uploads it to object storage. The URL importer blocks private/local addresses to reduce SSRF risk. Authenticated requests cannot redirect to another hostname. Query strings are not stored in provenance metadata.

This is appropriate for remote JSON/CSV responses and downloadable files. Future repository-specific adapters can add OAuth, pagination, manifests, signed URLs, and asynchronous imports.

## 6. API-client direct upload example

Request a presigned URL:

```bash
curl -s -X POST http://localhost:8000/api/uploads/presign \
  -H 'Content-Type: application/json' \
  -d '{
    "project_name":"Neuroblastoma Demo",
    "filename":"clinical.csv",
    "content_type":"text/csv"
  }'
```

The response contains `upload_url` and `object_key`. PUT the file directly to `upload_url` using the **same Content-Type** used while signing:

```bash
curl -X PUT '<UPLOAD_URL_FROM_RESPONSE>' \
  -H 'Content-Type: text/csv' \
  --upload-file ./sample_data/cohort_neuroblastoma/clinical.csv
```

Then complete registration:

```bash
curl -X POST http://localhost:8000/api/uploads/complete \
  -H 'Content-Type: application/json' \
  -d '{
    "project_name":"Neuroblastoma Demo",
    "filename":"clinical.csv",
    "content_type":"text/csv",
    "object_key":"<OBJECT_KEY_FROM_PRESIGN_RESPONSE>"
  }'
```

## 7. Import a public URL from the API

```bash
curl -X POST http://localhost:8000/api/import/url \
  -H 'Content-Type: application/json' \
  -d '{
    "project_name":"External Demo",
    "url":"https://example.org/cohort.json"
  }'
```

Bearer-protected GET API:

```bash
curl -X POST http://localhost:8000/api/import/url \
  -H 'Content-Type: application/json' \
  -d '{
    "project_name":"External Demo",
    "url":"https://api.example.org/v1/export",
    "filename":"api_export.json",
    "bearer_token":"REPLACE_WITH_TOKEN"
  }'
```

Do not commit tokens to Git or shell scripts.

## 8. Production S3 instead of MinIO

The code uses the S3 API. To use AWS S3 or another compatible provider, change the S3 environment settings and provide credentials through a secret manager/environment injection rather than committing them.

For browser-direct uploads, `S3_PUBLIC_ENDPOINT_URL` must resolve from the user's browser. Set bucket CORS to permit your actual application HTTPS origin and `PUT`, `GET`, and `HEAD` methods.

## 9. Security / research-data notes

This starter is **not yet an authorization boundary for controlled human-subject data**. Before handling controlled-access datasets, add at minimum:

- institutional authentication/SSO
- role-based project authorization
- audit logs
- encryption and managed secrets
- malware/file scanning where applicable
- data retention/deletion policy
- access logging
- controlled egress
- HTTPS everywhere
- repository-specific consent/access enforcement

Do not put real patient data, `.env`, credentials, FASTQ/BAM/CRAM, or object-store volumes in Git.

## 10. Suggested next milestones

1. **File profiling adapters** — CSV/TSV/JSON/FASTA/FASTQ/VCF/MAF/image metadata.
2. **Canonical model** — Study → Participant → Diagnosis → Specimen → Assay → File.
3. **AI harmonization** — suggested field mapping + confidence + Accept/Edit/Reject.
4. **QC dashboard** — missingness, duplicates, orphan samples/files, invalid controlled terms.
5. **Cohort builder** — reusable filters and cohort definitions.
6. **Background jobs** — Redis/Celery for FASTQ QC, VCF annotation, imaging metadata, model training.
7. **Auth + audit** — required before controlled-access data.
8. **Cloud deployment** — HTTPS Nginx + managed PostgreSQL + S3/object storage.

## Repository layout

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── storage.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── nginx/default.conf
│   └── Dockerfile
├── sample_data/
├── docs/
├── compose.yaml
├── .env.example
└── README.md
```

Research-use starter only; not clinical decision support.
