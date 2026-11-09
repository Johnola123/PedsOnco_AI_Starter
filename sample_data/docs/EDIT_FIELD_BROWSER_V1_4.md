# Edit field browser — v1.4

The Edit workspace no longer uses drag-and-drop for field selection. Editing is an explicit, reviewable operation:

1. Choose the cohort file.
2. Choose the exact worksheet/table when the file contains multiple tables.
3. Search or click a detected field.
4. Choose the edit operation.
5. Enter the new value/rule/note.
6. Review and confirm before provenance is recorded.

This is intentionally different from Harmonize and Integrate. Dragging remains useful where the user is visually matching one field to another, but it is unnecessary for a single-field edit target.

Field discovery was also widened. Excel and delimited files now discover up to 250 columns for field selection while keeping the visual preview compact (12 columns), so a wide CCDI workbook does not hide most fields from the editor.
