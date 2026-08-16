# DCAL annotation workbench runbook

## Scope

The workbench is the primary DCAL interface for building the institution-specific page dataset. It intentionally does five things:

1. receives rendered page images from the dedicated Google Drive pipeline or a pilot browser upload;
2. queues pages and shows annotation progress;
3. records physical document type, template variant, content profile, and image-quality defects;
4. records typed bounding boxes, reading order, legibility, stable field codes, and exact text;
5. validates completed pages and exports provenance-complete records to `dcal.gold.v1` JSONL.

It is not an electronic medical record, DCRP component, model runner, or frozen dataset registry.

## Hosted pilot

The production-shaped pilot lives in `web/` and is deployed with Vercel plus the DCAL-only Supabase project. It has named email/password accounts, inactive-by-default membership, annotator/reviewer/admin roles, private page storage, append-only revisions, optimistic locking, same-origin mutation checks, and server-mediated data access.

Follow [Hosted Deployment Runbook](DEPLOYMENT_RUNBOOK.md) for the one-time Supabase, Vercel, first-admin, and Drive-worker steps. Do not upload clinical material merely because the login page is reachable; complete the security and recovery gate in that runbook first.

## Private local compatibility start

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

Open `http://127.0.0.1:8090`. The default binding is loopback deliberately. Set an annotator display name in the top-right control; it is included in every revision and completed gold record. This local SQLite implementation is retained for development and recovery compatibility; it is not the Vercel deployment.

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

The hosted browser panel accepts one JPEG, PNG, or WebP page per request. Large images are resized in the browser to fit Vercel request limits, then normalized to PNG on the server. It accepts at most ten selected images per batch and sends them sequentially. These are pilot-only pages.

The local compatibility panel accepts JPEG, PNG, TIFF, WebP, BMP, and PDF. The Drive worker is the production path for every PDF and dataset-ready image. It normalizes sources to 300-DPI RGB PNG, limits source size/page count/pixel count, calculates SHA-256, and globally deduplicates identical rendered pages. Filenames are not stored or logged.

Browser uploads are deliberately not allowed to invent patient or encounter groups. To build the real dataset, upload into the dedicated Drive hierarchy documented in `GOOGLE_DRIVE_RUNBOOK.md` and run the ingestion profile.

## Drive ingestion

Start the workbench before the worker. Compose handles this through a health check:

```bash
docker compose --profile ingestion run --rm dcal-ingest doctor
docker compose --profile ingestion run --rm dcal-ingest sync-once
docker compose --profile ingestion up -d
```

The worker authenticates with the private bearer token, requests a two-hour signed upload destination from `POST /api/ingestion/upload-url`, uploads the canonical rendered PNG directly into the private bucket, and then calls `POST /api/ingestion/tasks`. A task key is derived from the rendered page checksum. Repeating ingestion returns the existing task. If an exact canonical-page or raw-image match from browser upload exists, Drive provenance upgrades that task to dataset-ready without replacing its annotation. A client-resized browser image may not match. The ingestion token is never a human login and the worker never receives the Supabase secret key.

## Export

Reviewers and administrators can select **Export gold** in the hosted header. Annotators cannot export. For the local compatibility server, run:

```bash
curl --fail http://127.0.0.1:8090/api/export/gold.jsonl \
  --output /secure/path/dcal-gold.jsonl
```

The response headers report exported and skipped-manual counts. Export includes only completed, Drive-provenance tasks. The file still contains clinical text and must remain in approved encrypted storage; never commit it to Git or attach it to a ticket/chat.

Gold export is not yet a frozen dataset release. M2 will add release manifests, patient/writer-separated splits, adjudication, and signed immutable snapshots.

## Storage and recovery

- The DCAL Supabase PostgreSQL database stores hosted task and append-only revision state; back it up separately from images.
- The private Supabase `dcal-pages` bucket is the hosted browser working copy. It is not canonical storage and currently has no one-command full restore path.
- `dcal_workbench_state` stores local-compatibility SQLite task and revision state.
- `dcal_page_cache` stores local checksum-addressed rendered PNGs. It is rebuildable from Drive.
- Google Drive stores the processed originals and canonical rendered pages.
- The ingestion ledger remains in `dcal_ingestion_state`.

Back up Supabase state and the ingestion ledger, and export reviewed gold snapshots to approved encrypted storage. For the local server, stop the workbench or use SQLite's online backup API before copying its database files; do not copy only the main file while WAL writes are active. The local page cache can be restored with `dcal-ingest restore-cache`. A Supabase restore must be tested before the pilot grows beyond data that can be safely re-ingested.

## Security boundary

The hosted implementation supplies the application controls below:

- HTTPS through Vercel and named Supabase Auth accounts;
- inactive-by-default profiles and role-gated export;
- same-origin mutation checks and server-side session revalidation;
- deny-all direct browser policies on tasks and revisions;
- a private page bucket accessed through authenticated server routes;
- separate human-session, Supabase-secret, Drive-credential, ingestion-token, and grouping-HMAC trust domains;
- response headers that disable caching, framing, referrers, and broad browser capabilities.

These operational gates are still mandatory before real clinical use:

- disable public signup, create users administratively, and review active accounts;
- store production secrets only in Vercel/worker secret stores and rotate them after suspected exposure;
- confirm Vercel, Supabase, Google Workspace, region, retention, and contractual choices with institutional information security;
- establish encrypted database backups, gold-export backups, restore drills, incident response, session revocation, and access-review cadence;
- monitor Supabase database/storage capacity and upgrade before the free tier becomes a reliability risk;
- optionally add an institutional network/VPN gate if policy requires it.

Do not solve the missing login by sharing the ingestion token with annotators. That token authorizes system-to-system task creation only.

## Operational checks

Before a pilot session:

```bash
curl --fail http://127.0.0.1:8090/api/health
docker compose --profile ingestion run --rm dcal-ingest audit-drive
```

During the first 50 pages of each physical type, record annotation time, unclear taxonomy choices, frequent box corrections, autosave conflicts, and completion errors. Do not widen the schema informally; adjudicate the pattern and version the contract when the change is real.
