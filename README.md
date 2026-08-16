# DCAL

DCAL is the standalone **Document Classification, Annotation, and Learning** laboratory for Bangladesh Medical College Hospital (BMCH) pages.

It is intentionally independent of DCRP. DCAL owns annotation, gold-dataset creation, experiments, evaluation, and model promotion. DCRP may consume a stable versioned inference API later, but it is not a dependency of this repository.

## Implemented foundation

- A first-party, browser-based annotation workbench with named Supabase authentication, role-gated export, private page delivery, upload, queue, progress, document identification, image-quality flags, drawable/resizable boxes, exact transcription, keyboard shortcuts, autosave, optimistic locking, and revision history.
- A versioned, repository-owned physical-document taxonomy.
- Deterministic export of completed, provenance-complete workbench pages to `dcal.gold.v1` JSONL.
- Dedicated Google Drive ingestion with PDF/image rendering, SHA-256 deduplication, opaque grouping IDs, quarantine, read-only archive locks, and idempotent workbench task creation.
- A persistent ingestion ledger, full Drive checksum audit, and complete reconstruction of the derived workbench page cache.
- Optional legacy Label Studio configuration and export adapter for compatibility; Label Studio is no longer the primary interface.
- Synthetic fixtures and CI checks. No patient pages or identifiable data belong in Git.
- A Vercel/Supabase hosted pilot in `web/`, with timestamped database migrations and a separate signed-upload contract for the Google Drive worker.

Not implemented yet: dataset release/split registry, RunPod model workers, active-learning selection, experiment tracking, model promotion, or DCRP integration.

## Challenger system

DCAL will use a champion-versus-challenger workflow for OCR, VLM, classification, transcription, layout, and structured extraction experiments. Challengers may come from OpenAI, Claude, local OCR, Gemini, rules-based preprocessing, or hybrid systems, but every challenger must run against the same frozen dataset snapshots and emit the same normalized prediction contract.

Read [Challenger Playbook](docs/CHALLENGER_PLAYBOOK.md) before building experiment runners, provider adapters, scoring, or promotion logic. Read [Winning Components](docs/WINNING_COMPONENTS.md) before proposing a challenger; it is the shared knowledge base where reusable wins from all challengers are recorded.

## Hosted deployment

The hosted pilot uses Vercel for the Next.js workbench and a DCAL-only Supabase project for named authentication, PostgreSQL task/revision state, and a private working-copy page bucket. The separate Google Drive remains the canonical intake and archive; one long-lived Docker worker connects it to the hosted workbench.

Follow [Hosted Deployment Runbook](docs/DEPLOYMENT_RUNBOOK.md) in order. The remaining account-owner actions are: add the server-only Supabase secret to Vercel, disable public signup, create and activate the first administrator, import the repo into Vercel with root `web`, create the separate Drive/credential, and start one ingestion worker. Do not put clinical material into the system until the runbook's security and restore gate is approved.

## Local compatibility start

Prerequisites: Docker with Docker Compose and Python 3.11 or newer.

```bash
cp .env.example .env
# Replace DCAL_WORKBENCH_INGEST_TOKEN with: openssl rand -hex 32
docker compose up -d
```

Open `http://localhost:8090`. Set your annotator display name, upload synthetic/pilot images or let the Google Drive worker populate the queue, then open a page.

The local SQLite workbench intentionally binds to `127.0.0.1` and has no human identity provider. Do not expose it to the internet. The hosted `web/` application is the multi-user path. Read [Workbench Runbook](docs/WORKBENCH_RUNBOOK.md) before handling real material.

The workflow is deliberately short:

1. Select the physical document type and page content profile.
2. Choose **Fixed**, **Variable**, **Writing**, **Choice**, or **Grid** and draw a box.
3. Select legibility, assign an optional stable field code, and transcribe visible text exactly.
4. Save a draft or complete the page. Every save is version checked and revisioned.

Browser uploads are marked **Pilot upload** and are excluded from gold export because they do not contain patient/encounter grouping. Pages entering through the dedicated Drive are marked **Dataset-ready**.

## Connect the dedicated Google Drive

Use one of these credential models:

1. **Recommended:** a Google Workspace Shared Drive with a service account. New service accounts do not have personal Drive storage quota, so a service account writing into an ordinary shared My Drive folder can fail.
2. A separate Google account using OAuth authorized-user credentials. Use this only when a Shared Drive is unavailable; the credential has broad access to that dedicated account.

Create one empty root folder or Shared Drive for DCAL and put its ID in `.env`. For OAuth setup:

```bash
python -m pip install -e '.[oauth]'
python scripts/authorize_google_drive.py \
  --client-secret /secure/path/oauth-client.json
```

Set `DCAL_DRIVE_ROOT_FOLDER_ID`, `DCAL_WORKBENCH_INGEST_TOKEN`, and a permanent `DCAL_GROUP_HMAC_KEY` in `.env`, then bootstrap and verify the Drive:

```bash
docker compose --profile ingestion build dcal-ingest
docker compose --profile ingestion run --rm dcal-ingest bootstrap-drive
docker compose --profile ingestion run --rm dcal-ingest doctor
```

Upload only into this hierarchy:

```text
00_INBOX/
  one-patient-folder/
    one-encounter-folder/
      scan.pdf
      phone-photo.jpg
```

Folder names remain inside Drive. DCAL derives stable HMAC identifiers from folder IDs and never sends raw folder IDs or names to the workbench.

Run once, then start continuous polling:

```bash
docker compose --profile ingestion run --rm dcal-ingest sync-once
docker compose --profile ingestion up -d
```

Verify archive integrity or rebuild the disposable annotation cache:

```bash
docker compose --profile ingestion run --rm dcal-ingest audit-drive
docker compose --profile ingestion run --rm dcal-ingest restore-cache
```

See [Google Drive Runbook](docs/GOOGLE_DRIVE_RUNBOOK.md) before connecting clinical material.

## Export annotations

From the workbench, use **Export gold**, or request the private local endpoint:

```bash
curl --fail http://127.0.0.1:8090/api/export/gold.jsonl \
  --output /secure/path/dcal-gold.jsonl
```

Only completed Drive-ingested pages are exported. Pilot browser uploads are counted but skipped.

The old Label Studio adapter remains available for prior exports:

```bash
python -m dcal_annotations validate-export examples/label-studio-export.valid.json
python -m dcal_annotations normalize-export \
  examples/label-studio-export.valid.json \
  --output /tmp/dcal-gold.jsonl
```

Install the package first when running outside this checkout:

```bash
python -m pip install -e .
```

## Tests

```bash
python -m unittest discover -s tests -v
```

Docker is not required for the Python and configuration tests. CI additionally validates Compose and builds the ingestion image.

## Non-negotiable data rules

- Never commit real patient images, exports, transcripts, identifiers, access tokens, or signed URLs.
- Originals are immutable and identified by SHA-256.
- A Google Drive read-only content restriction is a guardrail, not true write-once storage; run `audit-drive` and restrict Drive managers.
- Never change `DCAL_GROUP_HMAC_KEY` after ingestion begins without an explicit identity migration.
- `patient_group_id` and `encounter_group_id` are opaque keyed identifiers, not raw hospital IDs and not unsalted hashes.
- Unknown or unreadable content must be labelled as such; it must never be guessed into a known class or transcription.
- Test pages are separated by patient and writer and remain unavailable to model tuning.
- Workbench Supabase/SQLite state is operational state, not a frozen dataset release or model registry.

Read [Hosted Deployment Runbook](docs/DEPLOYMENT_RUNBOOK.md), [Workbench Runbook](docs/WORKBENCH_RUNBOOK.md), [Architecture](docs/ARCHITECTURE.md), [Google Drive Runbook](docs/GOOGLE_DRIVE_RUNBOOK.md), [Data Contract](docs/DATA_CONTRACT.md), [Annotation Guide](docs/ANNOTATION_GUIDE.md), [Challenger Playbook](docs/CHALLENGER_PLAYBOOK.md), [Winning Components](docs/WINNING_COMPONENTS.md), and [Roadmap](docs/ROADMAP.md) before extending the system.
