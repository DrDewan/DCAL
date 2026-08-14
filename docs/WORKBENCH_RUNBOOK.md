# DCAL annotation workbench runbook

## Scope

The workbench is the primary DCAL interface for building the institution-specific page dataset. It intentionally does five things:

1. receives rendered page images from the dedicated Google Drive pipeline or a pilot browser upload;
2. queues pages and shows annotation progress;
3. records physical document type, template variant, content profile, and image-quality defects;
4. records typed bounding boxes, reading order, legibility, stable field codes, and exact text;
5. validates completed pages and exports provenance-complete records to `dcal.gold.v1` JSONL.

It is not an electronic medical record, DCRP component, model runner, or frozen dataset registry.

## Private local start

Create configuration and secrets:

```bash
cp .env.example .env
openssl rand -hex 32
```

Put the generated value in both uses of `DCAL_WORKBENCH_INGEST_TOKEN` through `.env`. The token authenticates the ingestion worker, not human browser sessions.

Start the workbench:

```bash
docker compose up -d workbench
docker compose ps
```

Open `http://127.0.0.1:8090`. The default binding is loopback deliberately. Set an annotator display name in the top-right control; it is included in every revision and completed gold record.

For development without Docker:

```bash
export DCAL_WORKBENCH_INGEST_TOKEN="a-random-secret-of-at-least-24-characters"
python -m dcal_workbench \
  --database data/workbench.sqlite3 \
  --cache-root data/images
```

## Annotation screen

The queue distinguishes two provenance states:

- **Dataset-ready** — the Drive ingester supplied content hashes plus opaque patient and encounter grouping. A completed task may be exported.
- **Pilot upload** — the page came through the browser and has no trustworthy grouping. It can be used to test the UI and refine the taxonomy, but gold export skips it.

The annotation workspace contains:

- **Page identity:** physical document type, confirmed template variant, and content profile.
- **Quality flags:** clear or one/more material image defects. Clear cannot be combined with a defect.
- **Region tools:** fixed printed text, variable printed text, handwriting, choice/checkbox, and grid/other.
- **Canvas:** wheel zoom, Fit, Space-drag pan, box selection, box movement, and four-corner resize.
- **Region inspector:** type, reading order, legibility, structure, stable field code, and exact transcription.
- **Autosave:** saves after a short pause. `Ctrl/Cmd+S` saves immediately. A stale concurrent edit is rejected instead of overwriting another annotator.
- **Completion:** validates required page identity, region geometry, unique reading order, label/legibility compatibility, and required readable transcription.

## Printed-page protocol

Use these content profiles consistently:

| Content profile | Meaning | What to box |
|---|---|---|
| Blank printed form | Reusable form with no filled values | Representative fixed labels and all variable field locations |
| Printed form with typed values | Form populated by machine-printed values | Fixed template anchors plus each typed variable value |
| Fully printed document | Printed content that is not a fillable form | Meaningful text blocks in reading order |
| Printed form with handwriting | Printed template plus handwritten entries | Template anchors, field locations, and each handwritten line/value |
| Primarily handwritten page | No reliable printed template dominates | Handwriting lines or meaningful blocks |
| Not sure | Page profile cannot be defended | Annotate only defensible regions and explain in notes |

During template discovery, fixed boxes teach alignment anchors and establish canonical boilerplate. Once a template variant is registered, unchanged fixed boilerplate should come from the template registry; do not spend recurring annotation effort on it unless it drifted.

## Upload behavior

The upload panel accepts JPEG, PNG, TIFF, WebP, BMP, and PDF. The same production renderer normalizes pages to RGB PNG, limits source size/page count/pixel count, calculates SHA-256, and globally deduplicates identical rendered pages. Filenames are not stored or logged.

Browser uploads are deliberately not allowed to invent patient or encounter groups. To build the real dataset, upload into the dedicated Drive hierarchy documented in `GOOGLE_DRIVE_RUNBOOK.md` and run the ingestion profile.

## Drive ingestion

Start the workbench before the worker. Compose handles this through a health check:

```bash
docker compose --profile ingestion run --rm dcal-ingest doctor
docker compose --profile ingestion run --rm dcal-ingest sync-once
docker compose --profile ingestion up -d
```

The worker authenticates to `POST /api/ingestion/tasks` with the private bearer token. A task key is derived from the rendered page checksum. Repeating ingestion returns the existing task. If a matching browser-uploaded page exists, Drive provenance upgrades that task to dataset-ready without replacing its annotation.

## Export

Select **Export gold** in the header or run:

```bash
curl --fail http://127.0.0.1:8090/api/export/gold.jsonl \
  --output /secure/path/dcal-gold.jsonl
```

The response headers report exported and skipped-manual counts. Export includes only completed, Drive-provenance tasks. The file still contains clinical text and must remain in approved encrypted storage; never commit it to Git or attach it to a ticket/chat.

Gold export is not yet a frozen dataset release. M2 will add release manifests, patient/writer-separated splits, adjudication, and signed immutable snapshots.

## Storage and recovery

- `dcal_workbench_state` stores SQLite task and append-only revision state.
- `dcal_page_cache` stores checksum-addressed rendered PNGs used by the browser. It is rebuildable from Drive.
- Google Drive stores the processed originals and canonical rendered pages.
- The ingestion ledger remains in `dcal_ingestion_state`.

Back up the workbench SQLite volume and the ingestion ledger. Stop the workbench or use SQLite's online backup API before copying its database files; do not copy only the main file while WAL writes are active. The page cache can be restored with `dcal-ingest restore-cache`.

## Security boundary

The provided service is a private pilot baseline, not an internet-ready clinical application. It has no human login or authorization layer. Before binding beyond loopback or allowing multiple institutional annotators, all of these are mandatory:

- HTTPS and an identity-aware reverse proxy with named accounts;
- network restriction or VPN;
- role-based queue and export authorization;
- CSRF protection appropriate to the deployed authentication model;
- access logs that omit document content and identifiers;
- encrypted, tested database backups and restore drills;
- secret management instead of `.env` on a shared host;
- timeout/session-revocation policy;
- institutional information-security and data-governance approval.

Do not solve the missing login by sharing the ingestion token with annotators. That token authorizes system-to-system task creation only.

## Operational checks

Before a pilot session:

```bash
curl --fail http://127.0.0.1:8090/api/health
docker compose --profile ingestion run --rm dcal-ingest audit-drive
```

During the first 50 pages of each physical type, record annotation time, unclear taxonomy choices, frequent box corrections, autosave conflicts, and completion errors. Do not widen the schema informally; adjudicate the pattern and version the contract when the change is real.

