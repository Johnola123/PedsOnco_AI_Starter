# Direct upload and external import design

## Browser-local file path

```text
React
  | POST /api/uploads/presign {filename, content_type, cohort}
  v
FastAPI
  | generate_presigned_url(PUT)
  v
React
  | PUT file bytes directly
  v
MinIO/S3
  ^
  | POST /api/uploads/complete {object_key, metadata}
FastAPI -- HEAD object -- stream SHA-256 -- PostgreSQL register
```

### Why this path exists

Large oncology files should not be buffered through the web/API tier. The API authorizes/signs the operation, while object storage handles the payload.

## External URL/API path

```text
React / API client
   | POST /api/import/url
   v
FastAPI -- HTTPS GET --> external source
   | streaming hash/spool
   v
MinIO/S3 + PostgreSQL
```

A generic web browser cannot reliably fetch arbitrary remote resources because those sources may not permit CORS. Therefore remote-source imports are server-side in this starter.

## Security controls in the starter

- only `http`/`https`
- DNS resolution before requests
- private, loopback, link-local, multicast, reserved, and unspecified IP ranges blocked
- redirect destinations revalidated
- Bearer-authenticated imports cannot redirect to a different hostname
- Bearer token is not stored
- URL query string/fragment is not stored in provenance
- configurable maximum URL-import byte count

## Production requirements

- HTTPS for app and object storage
- user/project authorization before issuing presigned URLs
- short presign lifetimes
- S3 bucket policy scoped to application identities
- object-key prefix isolation by project/tenant
- upload size/type policy
- audit events for presign/import/download operations
- optional virus/malware scan and quarantine state
- asynchronous checksum/profiling for very large objects
