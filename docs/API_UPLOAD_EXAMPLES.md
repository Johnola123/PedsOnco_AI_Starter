# API upload examples

The interactive API documentation is available at `/docs` while the stack is running.

## A. Presigned direct upload

1. `POST /api/uploads/presign`
2. `PUT` bytes to returned `upload_url`
3. `POST /api/uploads/complete`

The `Content-Type` used for the PUT must match the value used when requesting the presigned URL.

## B. External URL/API import

`POST /api/import/url`

```json
{
  "project_name": "Cohort A",
  "url": "https://example.org/export.json",
  "filename": "export.json",
  "bearer_token": null
}
```

The current generic adapter performs HTTP GET. Add repository-specific adapters for APIs that require OAuth refresh, POST requests, pagination, asynchronous export jobs, or signed-manifest workflows.

## C. Short-lived download

`GET /api/datasets/{dataset_id}/download-url`

The returned URL lets the client retrieve the object directly from MinIO/S3 without routing the bytes through FastAPI.
