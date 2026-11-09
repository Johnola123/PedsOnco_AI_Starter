# Track 1 — Mac setup, public-data demonstration, and web validation

**Scope:** This guide is for the **updated code in this ZIP**, not for submission of identifiable patient information. The project uses a React frontend, a FastAPI API, PostgreSQL and MinIO. New Track 1 endpoints perform preliminary checks against a **user-supplied official CCDI workbook template**. They do not certify CCDI acceptance.

## 0. Requirements and limitations

- Mac with Docker Desktop (running), Docker Compose v2, and a modern browser.
- `git`, `unzip`, and Terminal; optional Python 3.11+ for backend tests.
- Download the latest approved CCDI DCC **metadata submission template XLSX** by navigating the official model repository and its `metadata-manifest` directory: https://github.com/CBIIT/ccdi-dcc-model . Confirm with CCDI curation staff which model/template release to use; **do not use an arbitrary sample workbook as an official template**.
- Start with public metadata, small processed tables, or the synthetic example files. **Do not upload controlled-access genomic data, protected health data, API tokens or patient identifiers into this demo.**
- The candidate package is **not** a direct dbGaP submission, official CCDI uploader, or fully verified ontology validator. The official process includes CCDI curator review, required/conditional metadata, consent/data governance, registration and designated storage.

## 1. Safely back up your original

```bash
cd ~/Documents/GitHub
cp -R PedsOnco_AI_Starter PedsOnco_AI_Starter_backup_$(date +%Y%m%d)
```

Download the updated ZIP and extract it. Rename its top-level extracted folder to `PedsOnco_AI_Starter_Track1` or merge individual changed files into a new git branch; do not blindly overwrite your existing development work.

```bash
cd ~/Documents/GitHub/PedsOnco_AI_Starter
 git checkout -b track1-ccdi-readiness
```

If you prefer replacing files, copy the updated `backend/app/ccdi.py`, `backend/app/main.py`, `frontend/src/CcdiReadiness.tsx`, `frontend/src/App.tsx`, `backend/tests/test_ccdi.py`, and docs into the corresponding paths. The ZIP is a complete copy of your originally attached project with additions.

## 2. Start the app

```bash
cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1  # change to your extracted directory
cp .env.example .env
```

Edit `.env` to use unique non-default local passwords for PostgreSQL and MinIO. Make sure `POSTGRES_PASSWORD` matches the password part of `DATABASE_URL`. Keep `.env` private, and never commit it. `S3_PUBLIC_ENDPOINT_URL=http://localhost:9000` must be reachable from the browser.

```bash
mkdir -p storage/minio
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs --tail=80 backend web
```

Open:
- Web interface: http://localhost:8080
- API Swagger docs: http://localhost:8000/docs
- Health endpoint: http://localhost:8000/api/health
- MinIO console: http://localhost:9001

Expected health JSON includes `"status": "ok"`. If browser says disconnected, inspect Compose logs; a healthy page alone does not prove API connectivity.

## 3. Baseline synthetic validation

1. Open **Add data** and make a cohort `TRACK1_DEMO_SYNTHETIC`.
2. Upload `sample_data/cohort_neuroblastoma/clinical.csv` and `specimens.tsv` (synthetic examples, not real TARGET participants).
3. Open the cohort; use **Inspect**, **Harmonize**, **Edit**, **Integrate**, **Explore**, and **Export**.
4. Review suggested canonical mappings manually. The existing harmonization UI has heuristic suggestions; it is **not** proven to be generative AI.
5. Confirm a cohort manifest can be exported, containing file/checksum provenance and workspace decisions.

## 4. Verify official public sources LIVE (web)

1. Open **CCDI readiness** in the navigation.
2. Under **Public source discovery**, choose **GDC project**, keep `TARGET-NBL`, click **Verify public accession**.
3. Check that the result contains `"public_metadata_only": true`, `"project_id": "TARGET-NBL"` and a valid GDC project response. It is a live request to the official `api.gdc.cancer.gov` service (network access needed).
4. Select **GEO study** and provide an actual public pediatric series accession `GSE...` that you verified on GEO; click **Verify public accession**. A `result_count` greater than zero confirms the GEO Series identifier resolves, **not** that the data are pediatric, freely downloadable or suitable for CCDI.
5. For source-file import, use **Add data → External URL/API** only on a direct, publicly downloadable file URL. A GEO *web page* or GDC *project page* is not a CSV file. Verify the content type and access rights. If a repository API returns a JSON envelope, import it as metadata, not a tabular expression matrix.
6. Record timestamp, source accession, source page link and screenshots. Public-source metadata discovery is separate from downloading full omics/imaging datasets; this release intentionally avoids automatic transfer of huge or controlled-access files.

Official resources:
- CCDI model/template: https://github.com/CBIIT/ccdi-dcc-model
- GDC API documentation: https://gdc.cancer.gov/developers/gdc-application-programming-interface-api
- GEO: https://www.ncbi.nlm.nih.gov/geo/
- TCIA: https://www.cancerimagingarchive.net/

## 5. Inspect real CCDI workbook structure

1. Download an **official**, current CCDI submission template `.xlsx` from the CCDI DCC model repository. Preserve its release/version and unmodified file.
2. Open **CCDI readiness → 1. Upload official CCDI .xlsx template**, choose file, click **Inspect official template**.
3. Review detected node sheets and properties; confirm expected `study`, `study_admin`, `study_funding`, `study_personnel`, `publication`, `consent_group`, `participant`, `diagnosis` sheets.
4. Review all warnings about headers and missing nodes. Metadata headers, formatting and reference sheets can vary by release: inspect manually if the detection fails.
5. Select a node such as `participant`; verify its field names before preparing mappings.

## 6. Candidate mapping and export

1. Prepare a **de-identified public or synthetic** CSV/TSV file with matching source columns; keep it under 10 MiB and 5,000 rows for this proof of concept.
2. Under **CCDI readiness → 2**, choose the CSV/TSV, enter a study/repository accession for traceability, select the target CCDI sheet.
3. Edit the JSON mapping. Example **only if the selected official template actually has these exact property names**:

```json
{
  "patient_id": "participant_id",
  "tumor_type": "diagnosis"
}
```

4. Click **Export candidate ZIP + QC + provenance**. The output contains:
   - `candidate_CC_DI_metadata.xlsx` — an official-template-based **candidate**, with the mapped rows populated on one empty target node sheet;
   - `validation_report.json` — preliminary structural/required-sheet checks;
   - `provenance_manifest.json` — source/template hashes, mapping and accession;
   - `README.txt` — curation disclaimer.
5. Open the workbook, verify target node row counts and values, complete other required and conditional CCDI sheets, and check controlled vocabulary against the actual template value-set/reference sheets.
6. **Do not call the workbook submission-ready yet.** The app does not enforce all actual required yellow cells, value sets, cross-sheet references, unique constraints, dbGaP records or image de-identification obligations.

## 7. Validate populated workbook

Use **CCDI readiness → 3. Validate an edited/populated metadata workbook**. Expected output is `preliminary-review-required` or `structural-errors`, not `CCDI approved`. Fix errors, inspect warnings and complete official CCDI curation handoff. A sheet-level passing status is not a substitute for manual scientific or regulatory validation.

## 8. Command-line smoke tests

```bash
curl -f http://localhost:8000/api/health
curl -f http://localhost:8000/openapi.json > /tmp/track1-openapi.json
curl -f 'http://localhost:8000/api/public-sources/gdc/project/TARGET-NBL'
curl -f 'http://localhost:8000/api/public-sources/geo/study/GSE12345'
```

Replace the GEO example with a verified series. A repository can be temporarily down or rate-limit queries; log that as an external dependency rather than a successful lookup.

To inspect an official CCDI template from Terminal:

```bash
curl -sS -F 'template=@/absolute/path/to/official_ccdi_template.xlsx' \
  http://localhost:8000/api/ccdi/inspect-template > template_inspection.json
python3 -m json.tool template_inspection.json | head -60
```

To run tests in a local Python virtual environment:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
PYTHONPATH=. pytest -q tests/test_ccdi.py
```

To verify the web build and start in Docker:

```bash
docker compose build web backend
docker compose up -d
docker compose logs --tail=100 web backend
```

## 9. Browser evidence capture for NCI

Capture at least six screenshots: (1) healthy cohort overview, (2) synthetic clinical/omics source files, (3) reviewed mapping and issues, (4) **live public GDC/GEO accession** verification, (5) official CCDI template node/field inspection, and (6) candidate ZIP/report/provenance output. Record versions, exact dataset accession, test date, commands and measured run time; never claim actual reduction in mapping labor without a measured manual baseline.

## 10. What this release DOES and DOES NOT prove

**Implemented:** Existing intake/profiling/cohort UI, heuristic mapping, source provenance, new CCDI workbook structure inspection, new public accession metadata lookup, source CSV/TSV-to-template candidate package, checksums, a preliminary validation report and backend tests.

**Not implemented / not yet verified:** official CCDI release-specific required-field and value-set engine, clinical consent auditing, complete relational cross-node validator, imaging header/risk mitigation checks, full GEO/GDC/TCIA file-adapter ingestion, browser-to-backend end-to-end test in this execution environment, CCDI curation acceptance, production multi-user authentication, restricted-data security, official S3 delivery, dbGaP submission, or measured harmonization performance improvement.

## 11. Common troubleshooting

- `docker: command not found` — install and start Docker Desktop.
- `Cannot connect to Docker daemon` — start Docker Desktop and rerun.
- `database disconnected` — check `DATABASE_URL`, PostgreSQL credentials, healthcheck and logs.
- `upload failed` — check MinIO console and `S3_PUBLIC_ENDPOINT_URL`, browser CORS and object-storage logs.
- `missing required CCDI sheets` — make sure this is the current official **metadata template**, not a small exported example.
- `source field not found` — CSV header keys are case-sensitive; compare with file's first row.
- `target property absent` — choose the exact property names shown by the inspected target node.
- `GDC/GEO 502` — verify internet/DNS/proxy and try the official public sites in a browser.
- Frontend TypeScript/build errors — rerun `docker compose build --no-cache web` with network access or `cd frontend && npm ci && npm run build`.

## 12. Publishing to GitHub safely

```bash
git status
git add README.md docs backend/app backend/tests frontend/src
# Add any license only after owner/institution confirms the chosen license.
git commit -m "Track 1 CCDI template readiness and public source metadata checks"
git push -u origin track1-ccdi-readiness
```

Never commit `.env`, object-store datasets, secret keys, controlled data, or uploaded genomic files. Arrange institutional approval for repository ownership, software licensing and submissions.
