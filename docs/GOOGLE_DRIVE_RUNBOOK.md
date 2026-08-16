# Dedicated Google Drive ingestion runbook

## Decision boundary

The selected pilot storage is a dedicated Google Drive, separate from DCRP and from personal/general institutional files. Google Drive is convenient for hospital upload workflows, but it is not object-lock storage. DCAL compensates with content hashes, checksum filenames, owner-restricted read-only content restrictions, an audit command, no automatic deletion, and a rebuildable local cache.

Do not describe this as cryptographically immutable. A Drive owner or Shared Drive manager can still unlock or delete content.

## Credential model

### Preferred: Google Workspace Shared Drive

1. Create a Shared Drive dedicated to DCAL.
2. Create a Google Cloud service account and enable the Google Drive API.
3. Add the dedicated service account to the Shared Drive as **Manager**. Google
   requires the organizer/Manager role to add or remove the stronger
   `ownerRestricted` content restriction used by DCAL. Do not reuse a general
   automation identity for this role.
4. Save its JSON credential outside the repository at `secrets/google-drive-credentials.json`.
5. Set `DCAL_DRIVE_ROOT_FOLDER_ID` to the Shared Drive root or a dedicated folder inside it.

The adapter sends `supportsAllDrives=true` on Drive operations. This path avoids relying on service-account personal storage quota. See Google's [Shared Drive API requirements](https://developers.google.com/workspace/drive/api/guides/enable-shareddrives).

### Fallback: separate Google account with OAuth

Use a separate account containing no unrelated files. Create an OAuth Desktop client, then run:

```bash
python -m pip install -e '.[oauth]'
python scripts/authorize_google_drive.py \
  --client-secret /secure/path/oauth-client.json \
  --output secrets/google-drive-credentials.json
```

The generated file contains a refresh token and is owner-readable only. It is still a high-value secret. The integration requests the full Drive scope because `drive.file` cannot reliably discover hospital files uploaded directly through the Drive UI.

## Generated folder layout

`dcal-ingest bootstrap-drive` creates or adopts these folders and marks each with a private Drive `appProperties` role:

| Folder | Purpose | Mutation policy |
|---|---|---|
| `00_INBOX` | Human/system uploads | New files only |
| `10_SOURCE_ARCHIVE` | Processed original PDF/image objects | Checksum-renamed and read-only locked |
| `20_PAGE_STORE` | Canonical 300-DPI rendered page PNGs | Content-addressed and read-only locked |
| `30_QUARANTINE` | Unsupported, encrypted, corrupt, or unsafe sources | Manual review only |
| `40_DATASET_EXPORTS` | Future frozen gold releases | Not used by ingestion yet |
| `90_MANIFESTS` | Future signed release manifests and audits | Not used by ingestion yet |

The bootstrap operation is idempotent. It refuses ambiguous duplicate folder roles.

## Required inbox structure

```text
00_INBOX/
  patient-folder/
    encounter-folder/
      source-1.pdf
      source-2.jpg
```

The actual folder names are never exported. DCAL applies a keyed HMAC to the Google folder IDs:

- patient folder ID → `patient_group_id`;
- encounter folder ID → `encounter_group_id`;
- source file ID plus page index/hash → opaque `source_object_id`.

Files directly inside `00_INBOX`, files directly inside a patient folder, or extra nested folders are layout errors and are not ingested. This strictness is deliberate: silently losing patient grouping would contaminate train/test splits.

The same patient must always use the same patient folder across encounters. Creating a new patient folder for an existing patient produces a different opaque group and can leak that patient across evaluation splits.

## Processing behavior

1. Enumerate patient and encounter folders.
2. Accept PDF, JPEG, PNG, TIFF, WebP, and BMP up to 250 MiB and 500 pages.
3. Reject encrypted PDFs, malformed files, decompression bombs, pages above 150 million pixels, and rendered PNGs above the hosted 25 MiB object limit.
4. Render PDF pages at 300 DPI and normalize all pages to RGB PNG.
5. Calculate raw-file and rendered-page SHA-256 values.
6. Globally deduplicate rendered pages by SHA-256.
7. Upload new rendered pages into `20_PAGE_STORE`, add provenance properties, and lock them read-only.
8. Materialize the page into the worker cache and, for the hosted workbench, upload it through a short-lived signed URL into the private Supabase working bucket.
9. Create or reuse one workbench task using a deterministic ingestion key. The worker uses a dedicated ingestion bearer token and never receives the Supabase secret key.
10. Move the original into `10_SOURCE_ARCHIVE`, rename it to its raw SHA-256, add provenance, and lock it.

Permanent source defects move to quarantine. Drive, network, workbench, or storage-contract failures leave the original in place and stop the current sync for later retry.

Run exactly one ingestion worker. The current pilot ledger and Drive query/create sequence are idempotent after crashes but are not a distributed lock for multiple simultaneous workers.

Pillow and PyMuPDF are exactly pinned because changing a renderer can change canonical PNG bytes and therefore page identities. Any renderer upgrade requires a new render profile and an explicit migration decision.

## Commands

For the hosted workbench, set `DCAL_WORKBENCH_URL` to its public HTTPS Vercel URL and use the exact same `DCAL_WORKBENCH_INGEST_TOKEN` in the worker and Vercel. Run only the ingestion service; it no longer requires a local workbench container:

```bash
docker compose --profile ingestion run --rm --no-deps dcal-ingest doctor
docker compose --profile ingestion run --rm --no-deps dcal-ingest sync-once
docker compose --profile ingestion up -d dcal-ingest
```

For a completely local compatibility stack, leave `DCAL_WORKBENCH_URL=http://workbench:8090` and start both services.

```bash
# Verify credentials and the six required folder roles.
docker compose --profile ingestion run --rm dcal-ingest doctor

# Process the current inbox once.
docker compose --profile ingestion run --rm dcal-ingest sync-once

# Start the workbench and the 60-second polling worker.
docker compose --profile ingestion up -d

# Download and checksum every archived original and page; also verify locks.
docker compose --profile ingestion run --rm dcal-ingest audit-drive

# Rebuild the local annotation page cache from 20_PAGE_STORE.
docker compose --profile ingestion run --rm dcal-ingest restore-cache
```

All routine command output is aggregate JSON. It does not print source filenames, folder names, Drive object IDs, transcripts, or tokens.

## Recovery and backup

- Google Drive holds original sources and canonical rendered pages.
- Hosted Supabase PostgreSQL holds tasks and annotation revisions; back it up independently and test recovery. The local compatibility server instead uses `dcal_workbench_state` and its SQLite WAL.
- `dcal_ingestion_state` contains the SQLite operational ledger; back up the volume, although task idempotency also reconciles against the workbench.
- `dcal_page_cache` is disposable and can be rebuilt with `restore-cache`.
- Preserve the HMAC key in a secure secret manager and an offline recovery record. Losing it makes new grouping identifiers incompatible with existing data.

Run `audit-drive` on a schedule and before freezing every dataset release. Any checksum mismatch or unlocked object blocks dataset promotion.

## Access controls

- Uploaders should access only the intake area needed for their work.
- Annotators normally require workbench access, not Drive access.
- Limit human Shared Drive manager/organizer roles because those users can remove
  content restrictions. The dedicated ingestion identity also has this power and
  must be treated as a privileged credential.
- Do not use public links.
- Hosted annotators use named, explicitly activated Supabase Auth accounts and do not receive Drive access. The local compatibility workbench still has no human authentication and must remain on loopback.

Google documents [custom `appProperties`](https://developers.google.com/workspace/drive/api/guides/properties), [content restrictions](https://developers.google.com/workspace/drive/api/guides/content-restrictions), and [resumable uploads](https://developers.google.com/workspace/drive/api/guides/manage-uploads).
