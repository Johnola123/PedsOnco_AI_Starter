# Cohorts, multi-sheet workbooks, and merged cohorts

## Cohort container
A cohort is identified by its cohort/project name. Any number of files can be added later to the same cohort, including clinical tables, JSON, sequence files, variants, images, and assay outputs.

## Excel workbooks
`.xlsx` and `.xlsm` files are inspected as multi-table containers. PedsOnco inventories every worksheet, preserves its name, counts rows/columns, and assigns a simple role such as study metadata, clinical, biospecimen, file metadata, reference, or other. It does not silently flatten all sheets into one table.

CSV and TSV remain single-table files. Multiple CSV/TSV files can still belong to the same cohort.

## Inspect / harmonize workflow
1. Add a workbook or other files to a cohort.
2. Open the cohort under **Inspect**.
3. Select a structured file and choose **Inspect**.
4. Review workbook sheets / JSON paths / table sizes.
5. Use this inventory as the input for canonical-field mapping and human-reviewed harmonization.
6. Add additional modalities later without changing the cohort identity.

## Merge cohorts
The **Merge** page creates a logical merged cohort across two or more source cohorts. Raw data are not copied, rewritten, or deleted. The merged cohort stores the source cohort names and presents their files as a combined view. This preserves provenance and supports harmonization-first cross-cohort analysis.

Recommended workflow: harmonize source cohorts first, review compatibility, then create a merged cohort.
