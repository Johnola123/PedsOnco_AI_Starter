# Human-in-the-loop harmonization — v1.3

Milestone 1 now implements a reviewable workflow:

**AI proposes → user visually reviews → user drags/edits → system validates → user confirms → provenance is recorded.**

## Proposal engine
The Milestone 1 proposal engine is intentionally transparent. It uses canonical-name matches, a maintained alias catalog, and partial name similarity to propose mappings with confidence and an explanation. It is labeled as an AI-assisted/semantic proposal MVP rather than a black-box production ontology model.

## Field-level interaction
- Source fields are draggable.
- Canonical targets are drop zones.
- Dragging a source field to a target changes that mapping to `Review` until explicitly accepted.
- Every drag action has a non-drag alternative through editable canonical fields/selectors.
- Workbook users choose the sheet/table before mapping; participant/clinical tables are preferred over README/reference sheets.

## Validation
`POST /api/harmonization/validate` checks:
- source field exists in the selected profile/table,
- accepted mappings have canonical targets,
- duplicate canonical targets,
- low-confidence mappings accepted by the reviewer,
- custom canonical fields,
- mappings still marked Review,
- at least one accepted mapping.

Validation returns a score, warnings, errors, and accepted/review/rejected counts. Blocking errors prevent confirmation.

`POST /api/integration/validate` checks that selected datasets differ and join keys exist in each profiled source. Key-name differences are surfaced as warnings.

## Confirmation and provenance
Nothing is persisted as an approved harmonization until validation passes and the user confirms. The saved workspace record includes:
- source dataset ID/name,
- selected sheet/table,
- full mapping decisions,
- proposal confidence and explanation,
- validation snapshot,
- confirmation timestamp,
- proposal-engine label.

Raw source objects remain immutable.

## Other drag/drop uses
- Upload files to a cohort.
- Drop a file into Inspect.
- Drag fields into non-destructive edit recipes.
- Drag files into integration source slots.
- Drag/select fields as integration join keys.

All primary drag interactions keep click/select alternatives for keyboard and mobile users.
