# Architecture notes

## Request path

```text
Browser
  |
  v
Nginx :80
  |-- /            -> React static build
  |-- /api/*       -> FastAPI :8000
  |-- /docs        -> FastAPI Swagger UI
  |
  v
FastAPI
  |-- metadata/provenance -> PostgreSQL
  |-- raw files/artifacts -> MinIO (S3-compatible)
```

## Separation of concerns

- PostgreSQL stores structured application metadata and relationships.
- MinIO/S3 stores large/raw data objects and derived artifacts.
- FastAPI owns validation, business logic, scientific services and API contracts.
- React owns the interactive user experience.
- Nginx presents one origin and routes traffic.
- Docker Compose runs the complete local stack reproducibly.

## Future service boundary

Add a worker/queue when analyses exceed normal HTTP request time:

```text
FastAPI -> Redis -> Celery/RQ worker -> MinIO/PostgreSQL
```

This is where FASTQ QC, VCF annotation, RNA-seq processing, model training and report generation should eventually run.
