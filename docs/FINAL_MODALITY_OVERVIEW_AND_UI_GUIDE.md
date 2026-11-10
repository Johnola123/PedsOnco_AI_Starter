# Track 1: modality-aware overview and final usability upgrade

## What's included

This is a full source snapshot based on `NCI_Track1_GEO_TCIA_CCDI_Connectors_2026_11_10.zip`, preserving the prior cohort workspace, source deletion and dependency confirmations, GEO/GDC importing, TCIA and CCDI read-only discovery, CCDI v2.2.0 preparation, cross-cohort merge, and deterministic evidence assistant.

New capabilities:

- **Data Overview**: responsive summary cards, modality counters, cohort filter and free-text search, compact dataset list, exported JSON summary.
- **Modality-aware summaries**: gene-expression metadata and matrix-layout candidates; clinical and outcome fields; participant/sample identifiers; imaging metadata fields; file-format-only recognition of raw imaging and sequencing files.
- **Dataset detail drawer**: three tabs for overview/structure, fields and identifiers, and preview-based missingness and caveats. Press Esc, click Close, or click outside the drawer to dismiss.
- **Field-level evidence**: shows which columns or CCDI sheet roles prompted a category. Gene-by-sample matrix candidates are recognized when gene-like identifiers and several sample-labelled columns occur together; not a guarantee of normalized expression or number of genes.
- **More accurate sample missingness**: columns not included in a narrow preview are now `not_sampled` rather than being incorrectly counted as 100% missing. The preview never represents full-file quality or unique-patient counts.
- **Simplified pages**: navigation grouped into Data & Discovery, Analysis & Review, and Submission Preparation; the global how-to-use hint collapses by default; Repository Explorer hides portal catalog details and long lists until requested.

## Limitations

- Raw DICOM, NIfTI, pathology slides, and FASTQ/BAM are **identified by extension** only. The application does **not** decode pixel data, assess image quality, process reads, or verify derived biological quantities.
- A field called `patient_id` or `sample_id` does not prove cross-dataset identity or uniqueness. No automatic patient deduplication is performed.
- Expression-matrix layout is a **candidate**, not a validated gene annotation or assay QC result. Many GEO Series Matrix files need custom parsers.
- Field completeness is estimated from cached preview rows. Full-file QC, ontology matching, and CCDI submission are distinct operations.
- No direct CCDI submission or authenticated transfer has been introduced. The **Complete local preparation** step still generates local handoff material, not a sync action.
- The Evidence Assistant remains a deterministic, local metadata assistant; no external generative AI call or transfer of protected information occurs.

## Mac migration (preserve current data)

1. Back up your project directory and Docker data volumes. Retain your existing `.env`, any local dataset files and the `storage/minio` folder.
2. Extract the ZIP into a **temporary folder**. It contains `PedsOnco_AI_Starter_Track1/`.
3. Copy updated `backend/`, `frontend/`, and `docs/` into your existing project. **Do not overwrite** your `.env` or accidentally replace directories containing live MinIO/PostgreSQL data. If you use custom compose settings, compare changes rather than replacing them blindly.
4. In your project folder:

```bash
cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1
docker compose config
docker compose up --build -d
docker compose ps
```

5. Check `http://localhost:8080` and `http://localhost:8000/docs`.
6. Navigate to **Cohorts → Workspace → Inspect** and profile a test CSV, TSV or Excel workbook. Then open **Data overview**; select the file to see tabs and category evidence.

**Do not use `docker compose down -v`** during upgrade. The change only derives classifications from cached profile JSON and does not require a SQL migration.

## Browser acceptance tests

- [ ] Existing cohorts, files, mappings and safe deletion confirmation still work.
- [ ] Navigation is grouped and `How to use this page` expands/collapses.
- [ ] Repository Explorer can search GEO/GDC; additional portal list is expandable.
- [ ] Overview loads and shows no false patient counts or inferred clinical outcomes.
- [ ] Import and inspect a `clinical.csv` with `patient_id`, `diagnosis`, `age_at_diagnosis`, `vital_status`: expected clinical and identifier categories.
- [ ] Import and inspect a `counts.tsv` containing `gene_id`, `GSM1234`, `GSM5678`: expected **expression matrix candidate** with sample-labeled headers, no claimed gene count.
- [ ] Import a metadata CSV with `SeriesInstanceUID`, `Modality`, `PixelSpacing`: expected imaging metadata only.
- [ ] Upload a `.dcm` object and profile: expected file-extension-only imaging categorization; no image pixel metadata claimed.
- [ ] For columns beyond the cached preview width, the detailed quality tab says *Not sampled* rather than 100% missing.
- [ ] Close dataset details with Esc and test a narrow/mobile viewport.
- [ ] Export JSON inventory and review source/provenance fields.
- [ ] CCDI v2.2.0 candidate validation and **local** handoff still work.

## Automated tests

Run locally after installing requirements:

```bash
cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1
python3 -m venv .test-venv
source .test-venv/bin/activate
pip install -r backend/requirements.txt pytest
PYTHONPATH=backend pytest -q backend/tests
cd frontend
npm ci
npm run build
```

The six dependency-light new tests can run without a database or external API:

```bash
python3 -m unittest discover -s backend/tests -p test_modality_overview.py -v
```

## Recommendation for later scientific work

When resources permit, add opt-in parsers for full expression matrices (gene annotation/orientation, gene/sample dimensions, nonzero/missing values), clinical schema validation, DICOM series metadata, and true row-level QC. Keep these different from metadata-only classification, and require permission and privacy checks before ingesting controlled-access datasets.
