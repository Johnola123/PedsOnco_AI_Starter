# CCDI v2.2.0 Track 1 implementation — user guide

## Start on macOS

1. Back up your current `PedsOnco_AI_Starter_Track1` folder and existing `.env` and volumes. Extract this release separately or merge source files after review.
2. `cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1`
3. If `.env` is absent: `cp .env.example .env` and set local credentials. Do not commit `.env`.
4. `docker compose config && docker compose up --build -d && docker compose ps`
5. Visit `http://localhost:8080`, open **CCDI preparation**; API docs: `http://localhost:8000/docs`.
6. Click **Use bundled CCDI v2.2.0 template**, then **Inspect template**. Expect **32 data-model node sheets**, **432 dictionary properties**, **100 value sets** in this inspected version. The official workbook has **35 total sheets** including 3 references.

## Single-table workflow

1. Optionally verify GDC project `TARGET-NBL` or a GEO Series accession; this **does not download source files**.
2. Select a public/de-identified CSV or TSV and enter the source accession. Select the target CCDI node.
3. Click **Suggest exact-name matches**, manually review every mapping, then **Download candidate ZIP + QC + provenance**.
4. Unzip locally, select `candidate_CC_DI_metadata.xlsx` in stage 5, and examine errors/warnings. The original workbook tabs and reference sheets are preserved.

## Multi-sheet workflow — new

1. In the **Multi-sheet import** panel, choose `sample_data/ccdi_v220_demo/source_tables.zip`.
2. Paste the complete contents of `sample_data/ccdi_v220_demo/mapping.json` into the mapping JSON field.
3. Click **Build multi-sheet candidate package**.
4. Unzip, review the generated workbook and QC JSON. The demo deliberately lacks many mandatory study and diagnosis fields; **local validation is expected to report gaps** rather than fabricating them.
5. Fix required fields and invalid controlled values in appropriate permitted source metadata, rebuild, then validate the resulting workbook again. Multiple valid linked node sheets will share de-identified participant IDs.

## Programmatic checks

From `backend/` with dependencies installed:

```bash
PYTHONPATH=. pytest -q tests/test_ccdi.py tests/test_ccdi_v220.py tests/test_large_profile.py
```

Docker routes: `POST /api/ccdi/inspect-template`, `POST /api/ccdi/build-candidate`, `POST /api/ccdi/build-multi-candidate`, `POST /api/ccdi/validate-workbook`, `GET /api/ccdi/reference-template`.

## CCDI handoff and limitations

The final **Complete local preparation** button downloads a local manifest only. **No direct NCI CCDI sync or submission** occurs. Official CCDI curation, controlled-access dbGaP processes, approved S3 provisioned upload and imaging risk mitigations remain separate. Contact `NCIChildhoodCancerDataInitiative@mail.nih.gov` to discuss tool delivery and permitted submission integration. Do not upload protected or controlled-access human data to an unauthorized service.

Current constraints: single and multi-node sources are limited to 10 MiB per file / 5,000 rows (multi ZIP ≤30 MiB); automatic GEO/GDC file downloads, full deep imaging ingestion and AI-generated ontology mapping are not implemented. Some datatype, consent and cross-repository provenance mappings require CCDI curator review. The demo does not demonstrate complete CCDI acceptance.

## Validation evidence

- 10 automated backend tests passed in the authoring environment, including inspection of the actual v2.2.0 workbook, type placeholder, relationship error and multi-node export.
- Frontend browser/build verification is pending on the Mac: the container's npm offline cache lacked the Vite package.
- Capture screenshots of a verified accession, template inspector, source mappings, validation report, candidate workbook, and local completion screen for a technical milestone evidence bundle.
