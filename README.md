# PedsOnco AI — Milestone 1 CCDI Interoperability Studio

A Git-ready, deployable feasibility application for the **Childhood, Adolescent and Young Adult Cancer Data Innovation Challenge — Phase I / Milestone 1**.

This repository intentionally focuses on the **Milestone 1 core**: demonstrate a credible, reusable approach for multimodal pediatric/AYA cancer data intake, CCDI-aligned harmonization, cohort exploration, provenance, integration, and export. The more experimental multi-institution federated-learning implementation is maintained separately in the `PedsOnco_Federation_Expansion` repository so the Milestone 1 demo stays simple, reviewable, and reproducible.

## Cohort workspace workflow (v1.3)

Every cohort is now a complete, non-destructive workspace:

**Files → Inspect → Harmonize → Edit → Integrate → Explore → Export**

- **Files** shows every asset added to the cohort, including later-added clinical, survival, molecular, sequence, imaging, and workbook files.
- **Inspect** profiles a selected file; Excel workbooks retain all worksheets as linked tables.
- **Harmonize** implements human-in-the-loop mapping: proposals → visual review → field drag/edit → backend validation → confirmation → provenance.
- **Edit** stores transformation recipes without overwriting raw source objects.
- **Integrate** records relationships between files/tables inside the same cohort, such as participant-to-survival or sample-to-expression keys.
- **Explore** summarizes file types, profiled tables, and table roles.
- **Export** produces a reproducible workspace manifest containing source provenance plus harmonization/edit/integration decisions.

**Cross-cohort merge is separate.** It creates a logical view across already prepared cohorts and does not replace within-cohort integration.

## Milestone 1 demonstration scope

- Cohort-centered multimodal intake
- Multi-sheet Excel/CCDI manifest inspection (all worksheets, not first-sheet only)
- CSV/TSV/JSON intake
- Registration of FASTA/FASTQ, VCF/MAF, BAM/CRAM, imaging/DICOM and other files
- Direct MinIO/S3 presigned uploads for large objects
- External URL/API ingestion
- Cohort-aware file provenance and checksums
- Dataset/workbook profiling
- Logical cohort merging without destroying source provenance
- Responsive React/TypeScript web interface
- Open-source Docker deployment

## Architecture

```text
Browser
   |
   v
Nginx -> React/TypeScript
   |
   v
FastAPI
   |---------------------- PostgreSQL (cohort/file metadata)
   |
   +---------------------- MinIO/S3 (large objects)
```

## Why federation is a separate repository

Federation is a valid Challenge direction, but a full multi-site federation adds site registration, governance, network trust, health monitoring, local training, aggregation, and privacy controls. Those features are maintained in a separate research repository so this Milestone 1 application can remain focused on a clean proof of feasibility. See `docs/MILESTONE2_3_ROADMAP.md`.

## Quick start

```bash
cp .env.example .env
mkdir -p storage/minio
chmod -R 777 storage/minio
docker compose config
docker compose up --build -d
docker compose ps
```

Open:

- App: http://localhost:8080
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001

## Suggested Milestone 1 demo

1. Add a synthetic cohort or a CCDI-style workbook.
2. Inspect every workbook worksheet and its role.
3. Add a second modality (JSON, VCF, FASTA, image, etc.) to the same cohort.
4. Harmonize a participant/clinical table: review proposals, drag fields onto canonical targets, accept/reject, validate, and confirm.
5. Integrate two within-cohort files using validated join keys.
6. Review provenance and export the workspace manifest.
7. Optionally create a separate cross-cohort logical merge view.

## Repository documents

- `docs/MILESTONE1_SCOPE.md`
- `docs/MILESTONE1_SUBMISSION_DRAFT.md`
- `docs/MILESTONE2_3_ROADMAP.md`
- `docs/CHALLENGE_ALIGNMENT.md`
- `docs/DEMO_SCRIPT.md`
- `docs/CCDI_SUBMISSION_READINESS.md`

## Important

This is a research software prototype. It is not clinical decision support and should not be used with identifiable patient data in an unsecured local development environment.


## v1.2 interaction update

- Drag-and-drop intake on Add Data.
- Drag-and-drop additional files directly inside a cohort workspace.
- Drop-to-inspect for rapid file profiling.
- Drag cohort file cards into left/right integration slots (selectors remain available for accessibility/mobile).
- In-app confirmation dialogs for removal of saved decisions, potentially consequential edit recipes, integrated views, and cross-cohort merges.
- Raw uploaded sources remain immutable; confirmations apply to working-layer/provenance operations.

## v1.3 human-in-the-loop harmonization

The cohort Harmonize workspace now implements the complete review path:

**AI proposes → user visually reviews → user drags/edits → system validates → user confirms → provenance is recorded.**

Source columns can be dragged onto CCDI-oriented canonical targets, edited manually, accepted/reviewed/rejected, validated by the FastAPI backend, and only then confirmed into an immutable workspace provenance record. Field-level drag/drop is also available for edit recipes and integration join keys, with keyboard/mobile selectors retained as alternatives. See `docs/HUMAN_IN_THE_LOOP_HARMONIZATION_V1_3.md`.

## v1.4 edit workspace

The Edit tab now uses an explicit table + searchable field browser instead of field drag-and-drop. This keeps editing safer and easier to understand: choose file → choose sheet/table → choose field → choose operation → review/confirm. Wide Excel/CSV/TSV sources now discover up to 250 columns for field selection while previews stay compact. Dragging remains available in Harmonize and Integrate where visual matching is useful.
