# NCI Track 1 – GEO/TCIA/CCDI discovery upgrade (November 2026)

## What is implemented

- GEO: live Series search and accession details (existing); NEW server-generated public file candidates from the official NCBI HTTPS `/matrix/` and `/suppl/` folders; user-selected processed-file import into a cohort; bounded gzip text previews.
- GDC/TARGET: existing study search, open-access file discovery, server-side access recheck and import.
- TCIA: NEW public v4 collection discovery and per-collection imaging modality lookup. Imaging file transfer, DICOM analysis, risk review and de-identification are **not** implemented.
- CCDI Federation: NEW read-only organization metadata lookup from the documented participating-node API. This is **not** an authorized submission or upload integration.
- St. Jude Cloud: official portal link only. Restricted genomic data require an authorized request. No undocumented API is assumed.
- Existing cohort workspace, harmonization, multi-sheet CCDI v2.2.0 readiness, safe deletion, comparisons, global dashboard and deterministic evidence assistant remain unchanged.

## Mac upgrade / migration

1. Back up your existing `~/Documents/GitHub/PedsOnco_AI_Starter_Track1` folder and keep a copy of your `.env` file. Do not copy credentials to GitHub.
2. Extract the ZIP to a temporary directory. Copy only the updated application source into the existing project directory, keeping `.env`, `storage/minio`, database volumes and any site-specific configuration unchanged.
3. Run:

   ```bash
   cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1
   docker compose config
   docker compose up --build -d
   docker compose ps
   docker compose logs --tail=100 backend frontend
   ```
4. Open `http://localhost:8080`. Go to **Explore Repositories**. Search GEO for `neuroblastoma`, choose a Series, review public processed-file candidates, select a small `.txt.gz`, `.csv`, or `.tsv` file, enter a cohort name and confirm import. Open the cohort workspace and inspect its preview.
5. Select **TCIA** and search a collection name (or leave the query blank to browse). Select a collection to inspect reported modalities.
6. Select **CCDI Federation** to view matching participating organizations. This does not register a site, modify CCDI or submit data.
7. The St. Jude card opens its portal; it does not automatically access restricted data.
8. Go to **Global Data Overview** and **Compare Cohorts**. Confirm that new imported files appear and that incomplete preview statistics are labeled as sampled.
9. Run backend tests:

   ```bash
   docker compose exec backend python -m pytest -q
   ```

   If pytest is not installed in the Docker backend image, run tests in your local Python environment after `pip install -r backend/requirements.txt pytest` and `PYTHONPATH=backend pytest -q backend/tests`.

## Safety and scientific interpretation

- Candidate files may not be suitable for tabular analysis. GEO supplementary data are heterogeneous and can require custom parsing or extraction.
- Only whitelisted GEO processed-file extensions are offered; directory names and filenames are validated server-side, and imports are checked against current public listings.
- The existing URL-import service enforces public-network IP validation, redirect limits, a configured byte ceiling, and SHA-256 hashing. It is intended for local testing, not a production-grade egress policy.
- Compressed `.txt.gz`, `.csv.gz`, `.tsv.gz` get an **up to 1 MiB decompressed preview**, not a full count, full missingness calculation or harmonized expression matrix.
- TCIA collection-level results do **not** represent unique patient counts.
- CCDI Federation read-only discovery does **not** authorize CCDI submission; official curation, institutional approvals and access-controlled upload steps remain separate.
- Do not send raw sequences, controlled-access data, identifiers, institutional secrets, or patient-level information to public generative AI services.
- This environment ran backend tests but could not build the frontend because npm dependencies are not cached. Browser and live remote-service checks must be performed locally.

## Deferred generative AI design (not enabled)

A future secure assistant should use institution-approved isolated model hosting; metadata-only retrieval with minimum-necessary data; source citations; strict permissions and role-based access; audit logging; prompt-injection defenses for retrieved metadata; no model training on controlled data unless explicitly approved; and human approval before mapping/export or workflow actions. The current deterministic evidence assistant remains available and should not be marketed as an active LLM integration.

## Official references

- NCBI GEO programmatic access: https://www.ncbi.nlm.nih.gov/geo/info/geo_paccess.html
- GEO file download instructions: https://www.ncbi.nlm.nih.gov/geo/info/download.html
- TCIA API guides: https://www.cancerimagingarchive.net/tcia-api-guides/
- CCDI Federation API: https://ccdi.stjude.cloud/api/v1/docs
- St. Jude data access: https://docs.stjude.cloud/genomics-platform/getting-started/making-a-data-request
