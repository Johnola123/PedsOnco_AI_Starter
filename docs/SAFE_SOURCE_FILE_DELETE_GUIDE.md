# Cohort files: safe Delete action

## What changed

Open a cohort → **Files**. Each file card now shows **Inspect | Harmonize | Download | Delete**.
Clicking **Delete** first calls `GET /api/datasets/{id}/delete-preview` to show the server's *actual* associated records. No data is deleted when the dialog opens.

The dialog lists:
- Uploaded original source object in this app's object storage, its filename and size.
- Imported-source metadata/provenance, if available.
- Cached inspection/profile and preview, if available.
- All saved harmonization, edit and integration records explicitly referencing this dataset ID.
- The count of other source files that will remain intact.
- Any logical cross-cohort views that reference the cohort. These views are retained but can become incomplete and need reevaluation.

**Cancel** and clicking outside the dialog only close it. **Yes, delete file and related data** calls `DELETE /api/datasets/{id}?confirmation_token=...`.
The confirmation token represents the list of referenced workspace records at the time of preview. If that list changes, the server returns HTTP 409; open Delete again to review the updated impact before confirming.

On successful deletion the UI refreshes the cohort, related records, and selected file state.

## Important limits

- This is a permanent deletion from *this app's* database and MinIO/S3 bucket. It cannot delete an upstream GEO/GDC study, other downloaded copies, or locally exported files.
- It only removes workspace records which explicitly reference the dataset by a recognized dataset ID field. Free-text references, previously downloaded manifest ZIPs, and manually managed objects outside the app are **not** removed.
- Logical cross-cohort views remain. Revalidate them after deleting their source data.
- If metadata removal succeeds but deleting the storage object fails, the API returns a storage warning and the server logs identify the orphaned object for administrator cleanup.
- This development prototype has no user authentication or per-cohort authorization. **Do not deploy destructive endpoints on a public or shared CCDI/NCI service** without identity, roles, audit logs, retention controls and backup policies.

## Mac installation

1. Back up your current project and data before updating.
2. Extract the ZIP into your GitHub folder; it contains `PedsOnco_AI_Starter_Track1`.
3. Preserve your current `.env` and persistent Docker volumes (database and object storage).
4. In Terminal:

```bash
cd ~/Documents/GitHub/PedsOnco_AI_Starter_Track1
docker compose config
docker compose up --build -d
docker compose ps
```

5. Visit `http://localhost:8080` → Cohorts → open a cohort → Files.
6. First test with a disposable test file; choose **Delete → Cancel** and verify it remains.
7. Choose **Delete** again, inspect listed dependencies and click **Yes, delete file and related data**. Confirm the file and linked records disappear and other files remain.

## Automated backend tests

```bash
cd backend
python -m pytest tests -q
```

Included tests cover: impact listing, stale-token rejection, dependent-record cleanup, and preservation of unrelated datasets. The backend tests passed in the artifact-building environment; a full browser build still needs testing on your Mac.
