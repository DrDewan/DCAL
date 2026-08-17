# DCAL

DCAL is the standalone **Document Classification, Annotation, and Learning** laboratory for Bangladesh Medical College Hospital (BMCH) pages.

It is intentionally independent of DCRP. DCAL owns annotation, gold-dataset creation, experiments, evaluation, and future model promotion. DCRP may consume a stable versioned inference API later, but it is not a dependency of this repository.

> **New AI/chat or developer? Start with [`docs/AI_HANDOFF.md`](docs/AI_HANDOFF.md).** It records the current deployed state, recent PR history, code map, known technical debt, continuation checklist, and verification sequence.

## Current state — 17 August 2026

The hosted first-party annotation workbench is live at:

`https://dcal-bm7i.vercel.app`

Current active milestone: **M1 — Secure ingestion and pilot**.

Implemented:

- First-party browser annotation workbench with named Supabase authentication, roles, queue, upload, page identity, image-quality flags, typed boxes, exact transcription, autosave, optimistic locking, and revision history.
- Structured **Table** annotation for investigation reports: draw one parent table rectangle and transcribe into a spreadsheet-style grid rather than drawing dozens of individual cells.
- Trackpad-friendly navigation: normal wheel/two-finger movement pans the page; pinch or `Ctrl/Cmd + wheel` zooms around the pointer; explicit Pan tool is available.
- Multiline text transcription with preserved line breaks.
- Versioned repository-owned physical-document taxonomy.
- Deterministic export of completed, provenance-complete workbench pages to `dcal.gold.v1` JSONL.
- Dedicated Google Drive ingestion code with PDF/image rendering, SHA-256 deduplication, opaque patient/encounter grouping IDs, quarantine, archive restrictions, idempotent task creation, persistent ledger, audit, and cache recovery.
- Vercel/Supabase hosted pilot under `web/` with timestamped database migrations and private signed-upload ingestion contract.
- Optional legacy Label Studio configuration/export adapter for compatibility only.
- Synthetic fixtures and CI checks. No patient pages or identifiable data belong in Git.

Still pending before M1 exit:

- further annotation usability refinement;
- verify/operate the production long-lived Drive worker before assuming dataset-ready ingestion is live;
- human pilot at roughly 50 pages per confirmed physical type;
- measured annotation time, taxonomy gaps, disagreement/correction patterns, and completion friction;
- security/recovery/access-review gates for scaling real clinical material.

Not implemented yet: frozen dataset release/split registry, RunPod model workers, active-learning selection, experiment tracking, model promotion, or DCRP integration.

## Immediate human annotation workflow

1. Select physical document type, optional template variant, and page content profile.
2. Mark image-quality defects.
3. Draw the natural annotation unit:
   - **Fixed** printed template text;
   - **Variable** printed patient/event-specific values;
   - **Writing** for handwriting;
   - **Choice** for checkbox/selection marks;
   - **Table** for investigation grids/charts;
   - **Other** for meaningful non-table regions.
4. Enter exact visible text or structured table cells.
5. Save a draft or complete the page.

For investigation tables, use **Table** (`T`) and draw one box around the complete table. The inspector then provides row/column controls and spreadsheet-style entry. See [`docs/TABLE_ENTRY_V2.md`](docs/TABLE_ENTRY_V2.md).

Navigation shortcuts include **Pan** (`P`), Space-drag, Fit, and pointer-centred pinch/Ctrl/Cmd-wheel zoom.

Browser uploads are marked **Pilot upload** and excluded from gold export because they lack trusted patient/encounter grouping. Pages entering through dedicated Drive ingestion are **Dataset-ready**.

## Important hosted client detail

The current hosted UI is deliberately layered:

- `web/public/app.js` — base browser workbench client.
- `web/public/ux-v2.js` — table entry, Pan/Table tools, trackpad navigation, inspector enhancements.
- `web/public/ux-v2.css` — UX v2 styles.
- `web/app/page.tsx` — loads the base script before the enhancement script.

Do not remove or reorder the UX v2 layer as a casual cleanup. A future consolidation should be a focused refactor with behavior tests.

## Hosted deployment

The hosted pilot uses Vercel for the Next.js workbench and a DCAL-only Supabase project for named authentication, PostgreSQL task/revision state, and private working-copy page storage. The separate Google Drive remains the canonical intake and source/rendered-page archive. A long-lived Docker worker connects Drive to the workbench.

Required runtime variable names and operating procedures are documented in [`docs/DEPLOYMENT_RUNBOOK.md`](docs/DEPLOYMENT_RUNBOOK.md). Never commit or document real secret values.

## Local compatibility start

Prerequisites: Docker with Docker Compose and Python 3.11+.

```bash
cp .env.example .env
# Replace DCAL_WORKBENCH_INGEST_TOKEN with: openssl rand -hex 32
docker compose up -d
```

Open `http://localhost:8090`.

The local SQLite workbench intentionally binds to `127.0.0.1` and has no human identity provider. Do not expose it to the internet. The hosted `web/` application is the multi-user product path. The local interface does not automatically include every hosted UX refinement.

## Dedicated Google Drive model

Use one of these credential models:

1. **Recommended:** Google Workspace Shared Drive + service account.
2. Separate dedicated Google account + OAuth authorized-user credentials when Shared Drive is unavailable.

Upload only into:

```text
00_INBOX/
  one-patient-folder/
    one-encounter-folder/
      scan.pdf
      phone-photo.jpg
```

Folder names remain inside Drive. DCAL derives stable HMAC identifiers from folder IDs and does not send raw folder names/IDs to the workbench.

Operational commands:

```bash
docker compose --profile ingestion build dcal-ingest
docker compose --profile ingestion run --rm dcal-ingest bootstrap-drive
docker compose --profile ingestion run --rm dcal-ingest doctor
docker compose --profile ingestion run --rm dcal-ingest sync-once
docker compose --profile ingestion up -d
docker compose --profile ingestion run --rm dcal-ingest audit-drive
docker compose --profile ingestion run --rm dcal-ingest restore-cache
```

See [`docs/GOOGLE_DRIVE_RUNBOOK.md`](docs/GOOGLE_DRIVE_RUNBOOK.md) before connecting clinical material.

## Gold export

Reviewers/admins can use **Export gold** in the hosted UI.

Local compatibility endpoint:

```bash
curl --fail http://127.0.0.1:8090/api/export/gold.jsonl \
  --output /secure/path/dcal-gold.jsonl
```

Only completed Drive-provenance pages are exported. Pilot browser uploads are skipped.

The old Label Studio adapter remains available for historical exports:

```bash
python -m dcal_annotations validate-export examples/label-studio-export.valid.json
python -m dcal_annotations normalize-export \
  examples/label-studio-export.valid.json \
  --output /tmp/dcal-gold.jsonl
```

A gold export is still operational output, not a frozen train/validation/test release. M2 will add immutable release manifests and patient/writer-separated splits.

## Tests

Root contracts:

```bash
python -m unittest discover -s tests -v
```

Hosted web app:

```bash
cd web
npm ci
npm test
npm run typecheck
npm run build
```

Docker/ingestion when available:

```bash
docker compose config
docker compose --profile ingestion config
docker compose --profile ingestion build dcal-ingest
```

GitHub CI checks both annotation and Compose/ingestion contracts. For hosted changes, also verify Vercel preview, `/api/health`, and production readiness after merge.

## Challenger system

Later milestones will use a champion-versus-challenger workflow for OCR, VLM, classification, transcription, layout, and structured extraction experiments. OpenAI, Claude, local OCR, Gemini, rules-based preprocessing, and hybrid systems must all use the same frozen dataset snapshots and normalized prediction contract.

Read [`docs/CHALLENGER_PLAYBOOK.md`](docs/CHALLENGER_PLAYBOOK.md) and [`docs/WINNING_COMPONENTS.md`](docs/WINNING_COMPONENTS.md) before building model/experiment runners.

## Non-negotiable data rules

- Never commit real patient images, exports, transcripts, identifiers, credentials, access tokens, or signed URLs.
- Originals are immutable and content-identified by SHA-256.
- Google Drive restriction is a guardrail, not true write-once storage; audit and restrict managers.
- Never change `DCAL_GROUP_HMAC_KEY` after ingestion begins without explicit identity migration.
- `patient_group_id` and `encounter_group_id` are opaque keyed identifiers, not raw hospital IDs or unsalted hashes.
- Unknown/unreadable content must be labelled as such; never guess it into a known class/transcription.
- Machine output never becomes human ground truth automatically.
- Test pages must stay separated by patient and writer and unavailable to model tuning.
- Supabase/SQLite workbench state is mutable operational state, not a frozen dataset release or model registry.
- Taxonomy changes must keep canonical config, web taxonomy copy, and compatibility aliases synchronized.

## Documentation reading order

For continuing work, read:

1. [`AGENTS.md`](AGENTS.md)
2. [`docs/AI_HANDOFF.md`](docs/AI_HANDOFF.md)
3. [`docs/ROADMAP.md`](docs/ROADMAP.md)
4. [`docs/DECISIONS.md`](docs/DECISIONS.md)
5. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
6. [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)
7. [`docs/WORKBENCH_RUNBOOK.md`](docs/WORKBENCH_RUNBOOK.md)
8. [`docs/TABLE_ENTRY_V2.md`](docs/TABLE_ENTRY_V2.md)
9. [`docs/DEPLOYMENT_RUNBOOK.md`](docs/DEPLOYMENT_RUNBOOK.md)
10. [`docs/GOOGLE_DRIVE_RUNBOOK.md`](docs/GOOGLE_DRIVE_RUNBOOK.md)

Then verify current GitHub/Vercel state before editing.
