# Track 1 UI refresh and CCDI handoff workflow (November 2026)

## What changed in this version

- New color-accented CCDI Preparation Studio with a six-stage progress tracker, illustrated workflow steps and accessible status messages.
- Guided public GEO/GDC project lookup. **Lookup retrieves public metadata only**. The interface links to the source repository for permitted file selection; it does not download source datasets.
- Source CSV/TSV header detection in the browser and a visual source-field → CCDI property mapping editor. `Suggest exact-name matches` provides literal header-name matching, **not AI/ontology mapping**. Manual review is mandatory.
- Official CCDI workbook inspection with discovered nodes and properties, warning/error counts and SHA-256 display.
- Candidate ZIP export with workbook, QC report and provenance, followed by local structural workbook validation.
- Final **Complete local preparation** button, gated on successful candidate ZIP export, local workbook check with no structural errors and explicit reviewer acknowledgment. It downloads `ccdi_local_handoff_manifest.json` and sets an on-screen local status; **it does not upload anything to CCDI**.
- **Request CCDI integration guidance** button opens an editable email to the official CCDI contact, without attaching patient information or datasets.
- Improved site-wide navigation (Cohorts, Add data, Workspace, Cross-cohort merge, CCDI preparation), hover/focus states and page-specific help banners. The preexisting cohort, profiling and edit operations are retained.

## Install or update on macOS

1. Save your old code and `.env`, and keep PostgreSQL/MinIO volumes. Do not run `docker compose down -v`.
2. Unzip the updated code into `~/Documents/GitHub/`. It creates `PedsOnco_AI_Starter_Track1`.
3. If this is a *new* installation, run `cp .env.example .env` and set your local passwords. If replacing a previous installation, keep your existing `.env` and storage volumes.
4. Open Docker Desktop; then:

```bash
cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1
docker compose config
docker compose up --build -d
docker compose ps
```

5. Visit http://localhost:8080. If you still see the old frontend, hard-refresh (Cmd+Shift+R).
6. Check `http://localhost:8000/docs` for the FastAPI routes.

## Step-by-step CCDI preparation demonstration

1. Open **CCDI preparation**.
2. Choose **NCI GDC / TARGET project** and enter `TARGET-NBL`, or choose GEO and use a *verified, relevant public* GEO Series accession. Select **Verify accession**. This confirms public metadata discovery only.
3. Click the study link to find an authorized public CSV/TSV metadata table. If direct download isn't available, use an allowed small public extract with source attribution. Controlled genomic data cannot be imported without authorization.
4. Upload the source table in stage 2. The UI displays source header names. Candidate export is presently limited to **10 MiB and 5,000 rows**; this is independent of the larger-file *preview* feature used in the cohort workspace.
5. Download the official CCDI metadata template from https://github.com/CBIIT/ccdi-dcc-model and upload the blank workbook in stage 3. Select the appropriate node and review the actual target properties.
6. Assign each source column to an actual target property in stage 4. `Suggest exact-name matches` is a convenience, **not AI**. Do not map unrelated concepts. Leave fields unmapped when uncertain. Export candidate ZIP.
7. Extract `candidate_CC_DI_metadata.xlsx` from that ZIP. Upload it in stage 5 and review all local structural warnings. Missing study-level and consent metadata may require additional manual curation.
8. When the package has been exported, the workbook has no locally detected structural errors, and the acknowledgment is checked, click **Complete local preparation**. Save the handoff manifest alongside your candidate ZIP. **No official sync has taken place.**
9. Click **Request CCDI integration guidance** to open a prefilled email describing the tool and requesting the approved hosting / data-transfer pathway. The email does not contain source datasets or credentials.

## CCDI hosting vs data submission: different integration contracts

**A. Tool hosting and distribution.** For Track 1, deliver code, instructions, dependencies, tests, licenses, example public/synthetic data, and evidence of repeatability through GitHub. CCDI may request NCI-approved hosting or cloud integration. The CCDI Hub lists many tools; adding a new tool to official Hub navigation requires NCI coordination. There is no general public self-registration/sync endpoint established in the cited guidance.

**B. Data contribution.** The CCDI Data & Tools Submission Guidance calls for the CCDI Metadata Submission Template, CCDI curation/review, supporting information, applicable institutional agreements, controlled-access dbGaP registration when relevant, and file transfer only to CCDI-provisioned storage (often S3). Public GEO/GDC metadata is not automatically new proprietary data. Do not bulk-copy or resubmit public datasets as if you own them.

**C. Data discovery/federation.** CCDI Data Federation Resource provides data discovery services; that is not the same thing as a write API. A future authenticated CCDI adapter should be **disabled by default**, require admin-provided credentials and a verified transfer destination, preflight validation, per-file checksum records, audit logs, explicit authorization, retry/status reporting, and confirmation receipts from CCDI. Never hard-code or commit credentials.

Official resources:
- CCDI guidance: https://ccdi.cancer.gov/Submission_Guide.pdf
- CCDI tools: https://www.cancer.gov/research/areas/childhood/childhood-cancer-data-initiative/data-ecosystem/platforms-tools
- CCDI federation API reference: https://ccdi.stjude.cloud/api/v1/docs
- CCDI model: https://github.com/CBIIT/ccdi-dcc-model
- CCDI contact: NCIChildhoodCancerDataInitiative@mail.nih.gov

## Verification and limitations

- Backend tests: `PYTHONPATH=backend python -m pytest backend/tests/test_ccdi.py backend/tests/test_large_profile.py -q` (six passed in the build environment).
- React TSX files passed TypeScript syntax transpilation with no parser diagnostics. A complete frontend typecheck / Vite bundle build could not be completed in the build environment because npm dependency fetching did not finish; rebuild with Docker on your Mac and review any build messages.
- The app was not deployed to the CCDI Hub; the **Request guidance** button starts a user-initiated email only.
- No live CCDI credentials, approved submission API, remote dataset sync, official CCDI acknowledgment, or full controlled-vocabulary validation have been configured.
- `Complete local preparation` is intentionally a local administrative milestone, not a compliance certification. A zero structural-error count is insufficient by itself for CCDI acceptance.

## Suggested next enhancements after initial validation

1. Add an actual public study-file browser and user-selected import for approved GEO/GDC assets, recording provenance and byte-range/streaming download state.
2. Make official template release version selection and CCDI value-set validation deterministic, with reviewer override/audit history.
3. Add missing-sheet completion forms for study, participant, diagnosis, consent and file nodes; preflight missing fields by modality.
4. Introduce an explicit administrator-only `Transfer to CCDI` action **only when the CCDI team supplies approved APIs/buckets, onboarding steps and credentials**.
