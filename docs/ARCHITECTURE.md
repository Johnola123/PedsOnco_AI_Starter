# Architecture notes

## Web request path

```text
Browser
  |
  v
Nginx :80
  |-- /            -> React static build
  |-- /api/*       -> FastAPI :8000
  |-- /docs        -> FastAPI Swagger UI
```

## Large/local file upload path

```text
1. Browser -> FastAPI: request presigned upload URL
2. FastAPI -> Browser: short-lived MinIO/S3 PUT URL
3. Browser -> MinIO/S3: upload bytes directly
4. Browser -> FastAPI: complete registration
5. FastAPI -> MinIO/S3: verify object + stream SHA-256
6. FastAPI -> PostgreSQL: dataset metadata/provenance
```

Nginx and FastAPI do not carry the initial large-file payload.

## External URL/API import path

```text
Browser/API client -> FastAPI -> external HTTP(S) source
                             -> MinIO/S3
                             -> PostgreSQL
```

This path is server-side because arbitrary external services may not expose browser CORS. The generic adapter supports GET plus optional Bearer authentication and applies SSRF protections.

## Separation of concerns

- **PostgreSQL** stores structured application metadata and relationships.
- **MinIO/S3** stores large/raw data objects and derived artifacts.
- **FastAPI** owns validation, presigning, registration, external-source ingestion, business logic and future scientific services.
- **React** owns the interactive user experience and direct browser uploads.
- **Nginx** serves the production UI and routes API traffic.
- **Docker Compose** runs the complete local stack reproducibly.

## Future service boundary

Add a worker/queue when analyses exceed normal HTTP request time:

```text
FastAPI -> Redis -> Celery/RQ worker -> MinIO/PostgreSQL
```

This is where multi-GB checksum jobs, FASTQ QC, VCF annotation, RNA-seq processing, model training and report generation should eventually run.
