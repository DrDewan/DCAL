# DCAL annotation workbench runbook

Read `AI_HANDOFF.md` first for the current deployed state and code map.

## Scope

The workbench is the primary DCAL interface for building the institution-specific page dataset. It intentionally does five things:

1. receives rendered page images from the dedicated Google Drive pipeline or a pilot browser upload;
2. queues pages and shows annotation progress;
3. records physical document type, template variant, content profile, and image-quality defects;
4. records typed bounding boxes, reading order, legibility, stable field codes, exact text, and structured tables;
5. validates completed pages and exports provenance-complete records to `dcal.gold.v2` JSONL.

It is not an electronic medical record, DCRP component, model runner, or frozen dataset registry.

## Hosted pilot

The production-shaped pilot lives in `web/` and is deployed with Vercel plus the DCAL-only Supabase project.

Current stable URL:

`https://dcal-bm7i.vercel.app`

The hosted workbench has named email/password accounts, inactive-by-default membership, annotator/reviewer/admin roles, private page storage, append-only revisions, optimistic locking, same-origin mutation checks, and server-mediated data access.

Follow `DEPLOYMENT_RUNBOOK.md` for Supabase, Vercel, users, secrets, and Drive-worker operations. Do not equate a reachable login page or successful Vercel build with institutional approval for unrestricted clinical use.

## Important browser-client architecture

The current hosted workbench browser client is intentionally layered:

- `web/public/app.js` — base client: queue, annotation state, canvas, drawing, move/resize, autosave, base keyboard handling.
- `web/public/ux-v2.js` — enhancement layer: Table tool, Pan tool, spreadsheet table editor, trackpad panning, pointer-centred zoom, inspector ordering/scroll isolation, multiline improvements.
- `web/public/ux-v2.css` — enhancement styling.
- `web/app/page.tsx` — loads base workbench first, then UX v2.

Do not casually remove, merge, or reorder this layer. Consolidation should be a dedicated refactor with behavior tests.

## Annotation screen

The queue distinguishes two provenance states:

- **Dataset-ready** — the Drive ingester supplied content hashes plus opaque patient and encounter grouping. A completed task may be exported.
- **Pilot upload** — the page came through the browser and has no trustworthy grouping. It can test the UI and refine taxonomy but gold export skips it.

The annotation workspace contains:

- **Page identity:** physical document type, confirmed template variant, and content profile.
- **Quality flags:** clear or one/more material image defects. Clear cannot be combined with a defect.
- **Region tools:** Fixed, Variable, Writing, Choice, Table, Other, plus Select and Pan.
- **Canvas navigation:** two-finger/normal wheel pan, pinch or `Ctrl/Cmd + wheel` zoom around the pointer, explicit Pan (`P`) drag, existing Space-drag/middle-button pan, Fit, region selection, movement, and four-corner resize.
- **Region inspector:** selected-region details appear first; type, reading order, legibility, structure, stable field code, exact transcription, or table editor.
- **Multiline transcription:** normal text preserves visible line breaks. The text area auto-grows within a bounded height.
- **Independent inspector scrolling:** the right sidebar scrolls separately and isolates wheel events from the canvas.
- **Autosave:** saves after a short pause. `Ctrl/Cmd+S` saves immediately. A stale concurrent edit is rejected rather than overwriting another annotator.
- **Completion:** validates page identity, geometry, unique reading order, label/legibility compatibility, required readable transcription, and structured-table requirements.

## Tool shortcuts

Current important shortcuts:

| Key | Tool/action |
|---|---|
| `V` | Select |
| `F` | Fixed printed text |
| `D` | Variable printed text |
| `H` | Handwriting |
| `C` | Choice / checkbox |
| `G` | Other meaningful region |
| `T` | Table |
| `P` | Pan |
| Space + drag | Pan |
| Delete / Backspace | Delete selected region |
| `Ctrl/Cmd+S` | Save now |

## Printed-page protocol

Use content profiles consistently:

| Content profile | Meaning | What to box |
|---|---|---|
| Blank printed form | Reusable form with no filled values | Representative fixed labels and all variable field locations |
| Printed form with typed values | Form populated by machine-printed values | Fixed template anchors plus typed variable values; use Table when a relational grid is the natural unit |
| Fully printed document | Printed content that is not a fillable form | Meaningful text blocks in reading order; use Table for structured reports |
| Printed form with handwriting | Printed template plus handwritten entries | Template anchors, field locations, handwritten lines/values, structured table when appropriate |
| Primarily handwritten page | No reliable printed template dominates | Handwriting lines or meaningful blocks |
| Not sure | Page profile cannot be defended | Annotate only defensible regions and explain in notes |

During template discovery, fixed boxes teach alignment anchors and establish canonical boilerplate. Once a template variant is registered, unchanged fixed boilerplate should come from the template registry; do not spend recurring annotation effort on it unless it drifted.

## Investigation tables and charts

For investigation reports such as haematology/biochemistry tables, do not draw dozens of independent cell rectangles unless there is a specific research reason.

Preferred workflow:

1. choose **Table** or press `T`;
2. draw one parent rectangle around the complete visible table;
3. set the row and column count;
4. specify whether a header row exists;
5. assign each non-header column a default content class: Fixed / Variable / Writing;
6. transcribe values into the spreadsheet-like editor.

Keyboard behavior inside the table editor:

- `Tab` moves to the next cell;
- `Enter` moves to the cell below;
- `Shift+Enter` inserts a line break inside a cell;
- pasting tab/newline-separated spreadsheet text fills a cell block and can expand the grid within contract limits.

A typical CBC layout may use:

- test name: Fixed;
- result: Variable;
- unit: Fixed;
- reference range: Fixed.

The parent region uses `label: "other_region"`, `structure_role: "table"`, and structured `table_data`. See `TABLE_ENTRY_V2.md` and `DATA_CONTRACT.md`.

## Writer identity

The inspector has an optional **Writer** section. If the page carries a legible signature, type the name as signed and press Add; if the writer is already registered, it is reused, otherwise a new registry entry is created.

Leave it empty whenever the signature is absent, illegible, or ambiguous. An empty value means "not recorded" and is a correct outcome; guessing a writer manufactures false grouping and corrupts writer-separated evaluation.

The name you type is stored only in the operational `public.writers` registry so annotators can select the same clinician consistently. The annotation and every gold record carry an opaque `wri_` identifier instead. Never put a clinician's name anywhere else in an annotation, including page notes.

## Upload behavior

The hosted browser panel accepts JPEG, PNG, or WebP pages. Large images are resized in the browser to fit hosted request limits, then normalized server-side. The UI can accept multiple selections and uploads them sequentially. These pages are pilot-only.

The local ingestion service accepts JPEG, PNG, TIFF, WebP, BMP, and PDF, which is why it is retained: the hosted upload route cannot accept PDFs inside a Vercel function (D-013). The Drive worker is the production path for every PDF and dataset-ready image. It normalizes sources to 300-DPI RGB PNG, limits source size/page count/pixel count, calculates SHA-256, and globally deduplicates identical rendered pages. Filenames are not stored or logged.

Browser uploads are deliberately not allowed to invent patient or encounter groups. To build the real dataset, upload into the dedicated Drive hierarchy in `GOOGLE_DRIVE_RUNBOOK.md` and run the ingestion profile.

## Drive ingestion

The implementation exists, but verify whether the production long-lived worker is currently running before assuming dataset-ready ingestion is live.

For local/worker operation:

```bash
docker compose --profile ingestion run --rm dcal-ingest doctor
docker compose --profile ingestion run --rm dcal-ingest sync-once
docker compose --profile ingestion up -d
```

The worker authenticates with the private bearer token, requests a short-lived signed upload destination from `POST /api/ingestion/upload-url`, uploads the canonical rendered PNG into the private bucket, then calls `POST /api/ingestion/tasks`.

A task key is derived from the rendered page checksum. Repeated ingestion returns the existing task. If an exact canonical-page or raw-image browser-upload match exists, Drive provenance upgrades that task to dataset-ready without discarding its annotation. A client-resized browser image may not match.

The ingestion token is never a human login and the worker never receives the Supabase secret key.

## Export

Reviewers and administrators can use **Export gold** in the hosted header. Annotators cannot export.

The hosted endpoint is `GET /api/export/gold.jsonl`. It requires an active reviewer or administrator session, streams `application/x-ndjson`, and orders records by canonical page checksum so two exports of unchanged state are byte-identical. Two response headers report what happened:

- `X-DCAL-Exported` — records written.
- `X-DCAL-Skipped-Invalid` — completed dataset-eligible rows that no longer satisfy the completion contract and were omitted. A non-zero value means stored annotation state drifted from the current taxonomy or validation rules; investigate before treating the file as a complete extract.

There is no local export path. Gold export exists only in the hosted workbench, where reviewer/admin roles are enforced against named accounts.

Every export is recorded in `public.page_access` with the actor, their role, and the record count, as is every page-image read. Reviewing that log is a deliberate database operation; the application exposes no interface for it.

Export includes only completed, Drive-provenance tasks. The file contains clinical text and must remain in approved encrypted storage; never commit it to Git or attach it to ordinary tickets/chats.

Gold export is not yet a frozen dataset release. M2 will add release manifests, patient/writer-separated splits, adjudication, and immutable snapshots.

## Private local ingestion service

Create configuration and secrets:

```bash
cp .env.example .env
openssl rand -hex 32
```

Put the generated workbench token in `.env`. It authenticates the Drive worker. The local service has no human authentication and no annotation interface, so it must stay on loopback.

Start:

```bash
docker compose up -d workbench
docker compose ps
```

The service exposes `/api/health`, `/api/uploads`, `/api/ingestion/tasks`, and read-only task/image inspection. There is no browser annotation UI; use the hosted workbench for annotation.

For development without Docker:

```bash
export DCAL_WORKBENCH_INGEST_TOKEN="a-random-secret-of-at-least-24-characters"
python -m dcal_workbench \
  --database data/workbench.sqlite3 \
  --cache-root data/images
```

The local SQLite implementation is retained for compatibility and recovery. It does not automatically include every hosted `web/` UX refinement.

## Storage and recovery

- Supabase PostgreSQL stores hosted task and append-only revision state; back it up separately from images.
- Private Supabase `dcal-pages` stores hosted working-copy page bytes; it is not canonical storage.
- Local `dcal_workbench_state` stores compatibility SQLite state.
- Local `dcal_page_cache` stores rebuildable checksum-addressed rendered PNGs.
- Google Drive stores processed originals and canonical rendered pages.
- `dcal_ingestion_state` stores the ingestion ledger.

Back up Supabase state and ingestion ledger, and export reviewed gold snapshots to approved encrypted storage. Test restore procedures before scaling the pilot.

## Security boundary

The hosted implementation supplies:

- HTTPS through Vercel and named Supabase Auth accounts;
- inactive-by-default profiles and role-gated export;
- same-origin mutation checks and server-side session revalidation;
- deny-all direct browser policies on tasks and revisions;
- private page bucket access through authenticated server routes;
- separate human-session, Supabase-secret, Drive-credential, ingestion-token, and grouping-HMAC trust domains;
- response headers that disable caching, framing, referrers, and broad browser capabilities.

Operational gates remain mandatory:

- public signup disabled;
- users created/activated administratively;
- production secrets only in approved secret stores;
- encrypted database and export backups;
- restore drills;
- incident response/session revocation;
- access-review cadence;
- storage/capacity monitoring;
- institutional review of hosting region, retention, and contractual requirements.

Do not solve a missing login by sharing the ingestion token with annotators.

## Verification

Before declaring a hosted change complete:

```bash
python -m unittest discover -s tests -v
cd web
npm ci
npm test
npm run typecheck
npm run build
```

When relevant and Docker is available:

```bash
docker compose config
docker compose --profile ingestion config
docker compose --profile ingestion build dcal-ingest
```

Then verify GitHub CI, Vercel preview readiness, `/api/health`, and the production deployment after merge.

During pilot sessions, record annotation time, unclear taxonomy choices, frequent geometry corrections, table-entry friction, navigation friction, autosave conflicts, and completion errors. Do not widen the schema informally; adjudicate repeated patterns and version the contract when the change is real.
