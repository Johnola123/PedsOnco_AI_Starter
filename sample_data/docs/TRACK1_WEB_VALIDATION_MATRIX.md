# Track 1 web validation and evidence matrix — November 2026

| Requirement / claim | Primary authoritative web source | Software status | What still needs proving |
|---|---|---|---|
| Track 1 permits shovel-ready tools; functional demonstration encouraged | NIH challenge: https://www.nih.gov/challenges/childhood-adolescent-young-adult-cancer-data-innovation-challenge | Existing deployed architecture in user ZIP; new changes added | Local Docker browser smoke test, objective demonstration metrics |
| CCDI models and metadata manifests are versioned | Official CCDI DCC model: https://github.com/CBIIT/ccdi-dcc-model | Inspects user-supplied workbook without claiming version verification | Record official release/tag; inspect actual current workbook |
| Required CCDI metadata node sheets | User-supplied CCDI Data & Tools Submission Guidance (pages 2–3) | Checks eight mandatory sheet names; can populate one node | Required yellow-cell rules and per-node/conditional requirements not enforced |
| Data dictionaries and controlled vocabularies | CCDI Submission Guide and model value set references | Exposes header fields only | Version-pinned dictionary/enum checks and ontology resolution |
| Public genomic data via GDC API | GDC developer API: https://gdc.cancer.gov/developers/gdc-application-programming-interface-api | Fixed-host public project lookup | Live status test from user's Mac; clinical/biospecimen multi-entity ingest not included |
| Public transcriptomic discovery via GEO | GEO: https://www.ncbi.nlm.nih.gov/geo/ and NCBI E-utilities | Fixed-host GEO accession existence lookup | Select pediatric accession, verify public study suitability; actual expression data ingestion |
| Imaging data | TCIA: https://www.cancerimagingarchive.net/ | Existing generic image/file intake only | TCIA adapter, DICOM inspection, risk mitigation and de-identification validation |
| Open-source GitHub distribution | NIH challenge and CCDI Submission Guide | Git-ready ZIP, no project-specific license confirmed | Institution/owner must confirm license and publish repository |
| dbGaP and delivery | CCDI Submission Guide sections on dbGaP and S3 | No controlled-access submission function; deliberately excluded | CCDI-curated registration and credentials, approvals, upload |
| Proof of scalability and time savings | NIH challenge preliminary-data requirement | Four small backend tests pass in current environment | Collect real latency, accuracy, file size, manual baseline and independent review |

**This matrix summarizes authoritative website requirements and software implementation; it does not claim that the modified application has been approved, externally verified by NCI, or live-deployed.**
