# Cohort Workspace v1.1

PedsOnco AI now treats the cohort as the primary working unit.

## Workflow

1. **Files** — see all assets associated with the cohort, including files added after the initial workbook.
2. **Inspect** — profile workbooks, CSV/TSV, JSON, and retain metadata for large specialized files.
3. **Harmonize** — generate transparent field-mapping suggestions, review them, and persist decisions.
4. **Edit** — save non-destructive transformation recipes such as rename, value mapping, datatype conversion, filtering, deduplication, or annotations.
5. **Integrate** — define key relationships between files/tables inside one cohort.
6. **Explore** — summarize file/modalities and profiled CCDI-oriented table roles.
7. **Export** — download a JSON workspace manifest containing provenance and all reviewed decisions.

## Provenance model

Raw uploaded objects are immutable. Harmonization mappings and edit/integration decisions are stored in `cohort_workspace_records`. This creates three conceptual layers:

`Raw source -> reviewed working layer -> analysis-ready integrated/derived view`

## Cross-cohort merge

Cross-cohort merging remains a separate operation. It produces a virtual traceable view across source cohorts rather than physically changing source data.
