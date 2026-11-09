# Track 1 — large-file preview fix and accession workflow (Nov. 2026)

## Why the 243 MiB error appeared
The original `backend/app/profiling.py` rejects structured files over 75 MiB. The object itself may be valid. This release retains the small-file behavior, uses bounded streaming for larger CSV/TSV files, uses temporary disk and openpyxl read-only mode for larger Excel workbooks up to 512 MiB, and returns metadata-only status for large JSON. A sampled preview is NOT full-file QC or a full row count. Very large or complex workbooks can still take considerable disk/CPU time; split them if necessary.

## Update your Mac repo
1. Back up your original project and extract this update into its own directory.
2. In Terminal:
```bash
cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1
cp .env.example .env  # only on a fresh install; preserve any existing real .env
mkdir -p storage/minio
docker compose up --build -d
docker compose ps
```
3. Open `http://localhost:8080` and select your original cohort and 243 MiB dataset. Retry **Profile** (use refresh if a cached profile exists). For a CSV/TSV, a limited sample and `row_count_complete=false` should appear rather than HTTP 413. If you used an Excel workbook, expect read-only processing using temporary disk.
4. View errors:
```bash
docker compose logs --tail=100 backend
```
5. Run backend tests where dependencies exist:
```bash
cd backend
PYTHONPATH=. python -m pytest -q tests/test_ccdi.py tests/test_large_profile.py
```

## After repository + accession (current behavior)
1. Select GDC `TARGET-NBL` or a GEO Series accession and press Verify.
2. The response confirms discovery of **public metadata only**. It is *not* an automatic download or import; the page now says this plainly and opens the repository record.
3. From the repository, select/download a permitted public clinical/sample metadata CSV/TSV. For GEO, check the Series page for supplementary files and whether they are truly public. Avoid assuming every GEO Series has ready-to-use patient clinical records.
4. Get the official versioned CCDI XLSX template from https://github.com/CBIIT/ccdi-dcc-model . Inspect it using the page's Upload official CCDI .xlsx template control.
5. Select a CCDI target sheet, upload the small source CSV/TSV, set source accession, and enter reviewed source-header-to-target-header JSON.
6. Export candidate ZIP (candidate workbook, validation report, provenance manifest). Review missing mandatory fields and related nodes; do not present the resulting workbook as complete or approved.
7. If you have edited the workbook, use Validate edited/populated metadata workbook. Present its issues as preliminary structural validation only.

## Remaining development (not included)
- Accession-to-study import with permissioned file selection, ingest into cohorts, and checksums.
- Version-pinned CCDI dictionary/vocabulary and required-value validation.
- Formal CCDI curator review, legal data sharing approval, dbGaP registration, approved S3 submission.
- TCIA imaging adapter and governed PHI/controlled data workflows.

## Known implementation notes
- The bounded CSV/TSV reader extracts only a small sample of rows to prevent excessive memory use. It does not count all records or calculate global missingness.
- Large JSON is not parsed; it is registered and marked metadata-only.
- The frontend changed the GEO/GDC lookup display from raw JSON to a concise status with an external source link and next-step instructions. It does not import datasets automatically.
