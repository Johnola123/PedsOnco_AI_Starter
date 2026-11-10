# Track 1 A–H discovery and analytics expansion — November 2026

## Overview
This release extends the **existing** React/FastAPI/PostgreSQL/MinIO application rather than replacing its cohort workspace, original objects, safe delete, harmonization, or CCDI v2.2.0 preparation. It adds a navigable repository explorer, cached-profile inventory, schema comparison, and evidence assistant. Local completion **never transfers data to CCDI**.

## Honest feature-by-feature delivery status

| Requested package | Delivered now | Remaining for production-grade completion |
| --- | --- | --- |
| **A — Repository Explorer** | Live NCBI GEO Series keyword search, GEO metadata details; GDC project search, project open-file listing; searchable cards and official links | More metadata facets, GEO sample/file enumeration, saved searches/pagination |
| **B — Public Import** | Select public GDC files and import into cohort via existing bounded URL import; backend rechecks `access=open` | GEO processed-file chooser (currently use existing URL import), resumable transfers, independent checksum verification against remote MD5 |
| **C — Data Dashboard** | Source object inventory, origin, cohort/format totals, cached schema fields, preview-only missingness, JSON export | True full-file missingness, demographics, gene matrices, image QC, source deduplication |
| **D — Comparison** | Two to eight files; shared/union/exclusive schema fields and warnings | Ontology-aware/unit-aware compatibility and row-level cohort linkage |
| **E — Additional repositories** | Discovery registry/official links for TCIA, St. Jude Cloud, CCDI, SRA, Kids First, dbGaP | Live API adapters and selected-file ingest for these providers; access/terms review required |
| **F — Assistant** | Deterministic metadata-grounded Q&A on counts, preview completeness, handoff | Actual generative AI model is **not enabled**; a vetted private/safe model, institutional approval, and citation evaluation are required |
| **G — UX** | Responsive colorful explorer, filters, statistics cards, comparison selectors, status and download controls | Full browser usability/accessibility evaluation |
| **H — CCDI** | Existing v2.2.0 local validation/export, completion handoff retained; links and warnings clarified | Authorized CCDI ingest/sync/SSO requires direct agreement and credentials from CCDI |

## Before upgrading an existing deployment
1. Back up repository and current `.env`. Maintain current database and MinIO storage **unchanged**.
2. Back up Postgres using your existing credentials and `docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql` from an environment with the vars exported, or an equivalent backup process.
3. Keep the original `postgres_data` named volume and the mapped `./storage/minio` directory. **Never run `docker compose down -v`**, and do not delete `storage/`.
4. Confirm your new extracted folder uses the same compose project name/working directory if you want to reconnect existing volumes. Changing the directory may create a **new** Postgres volume. To avoid that, copy only changed source files into your original repo or specify `docker compose -p <existing_project> ...` with the exact existing project name.

## Upgrade in place on Mac

```bash
cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1
# Back up your current code and .env first. Copy updated app code into this exact directory.
# Only on a fresh deployment with no .env:
cp .env.example .env
# In .env, set strong secrets; DATABASE_URL password must match POSTGRES_PASSWORD.
mkdir -p storage/minio
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs --tail=80 backend web
```

- App: http://localhost:8080
- Swagger: http://localhost:8000/docs
- Check `GET /api/health`.
- Existing tabs should remain: Cohorts, Add Data, Workspace, Cross-cohort Merge, CCDI Preparation.
- New tabs: Explore Repositories, Data Overview, Compare Datasets, Evidence Assistant.
- **No SQL migration** is needed; this release adds read-only queries/endpoints and reuses `datasets`, `dataset_sources`, `dataset_profiles`, and the existing object store.

## End-to-end smoke tests
1. Open **Explore repositories**, choose GEO, search `neuroblastoma`, select a GSE entry. Verify title, abstract, accession, and official source link. GEO file selection is **not yet automatic**.
2. Choose GDC, search `TARGET` or `TARGET-NBL`. Open a project and review the **open-access** file list. Choose a small public metadata file, select cohort, click Import. Import enforces existing URL size limits. If the remote source denies or fails the transfer, no successful import should be displayed.
3. Open **Cohorts → Workspace → Inspect** and profile the imported file. Return to **Data Overview**; verify origin, format, field list, and **preview-only** missingness. Download JSON inventory.
4. Profile two CSV/TSV datasets. Open **Compare Datasets**, select both; inspect shared/exclusive field names and caution about non-equivalent semantics.
5. Open **Evidence Assistant**. Ask "How many datasets are loaded?", "What is missingness?", and "Can I sync to CCDI?". Verify local, deterministic answers and no outbound LLM request.
6. Open **CCDI Preparation**, select the bundled 2.2.0 template, build/validate the candidate, complete local preparation. Confirm **no external CCDI upload** occurs.
7. In an expendable cohort, use **Delete**; click Cancel and verify nothing changes. Confirm Yes, verify the dependency list and that unrelated files remain.

## Test suite

```bash
cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt pytest
PYTHONPATH=backend pytest -q backend/tests
cd frontend
npm ci
npm run build
```

The backend tests run against mocked public repository responses, not live external APIs. A live Mac/browser test and repository API testing remain required. If network access or institutional access policy blocks external sources, use the official portal links instead.

## API overview

- `GET /api/discovery/sources` — provider metadata + honest integration mode
- `GET /api/discovery/search?source=geo|gdc&q=...&limit=20` — live study search
- `GET /api/discovery/geo/GSE...` — GEO summary
- `GET /api/discovery/gdc/TARGET-NBL/files` — open-access GDC file list
- `GET /api/discovery/gdc/file/{uuid}/verify` — recheck `access=open`
- `POST /api/discovery/gdc/import-open-file` JSON `{"file_id":"<uuid>","cohort":"My Cohort"}` — bounded import
- `GET /api/analytics/overview` — cached-profile inventory (not full-file QC)
- `GET /api/analytics/compare?ids=1,2` — schema-field comparison
- `POST /api/analytics/explain` JSON `{"question":"..."}` — deterministic evidence assistant

## Security and scientific limits
This prototype has **no complete multi-tenant auth/RBAC or institutional audit controls**. Do not deploy as a shared clinical system or ingest restricted data without approved controls. Remote GDC access must be open; no tokens are collected through its auto-import. Do not count source-file counts as unique participants. Sampling-based missingness cannot substantiate CCDI readiness. Do not assume matching column names imply equivalent biology, assay, units, or consent permissions.

GDC submission endpoints belong to GDC and are **not** automatically CCDI-approved ingestion. An NCI CCDI submission requires metadata curator review and authorized storage/access. "Complete local preparation" produces artifacts only.

## Official references
- GDC API: https://docs.gdc.cancer.gov/API/Users_Guide/Getting_Started/
- NCBI E-Utilities: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- TCIA APIs (v4 documentation): https://www.cancerimagingarchive.net/tcia-api-guides/
- CCDI data federation: https://ccdi.cancer.gov/data-federation-resource
- CCDI v2.2.0 model: https://github.com/CBIIT/ccdi-dcc-model
