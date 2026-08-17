# DCAL AI continuation handoff

**Snapshot date:** 17 August 2026  
**Repository:** `DrDewan/DCAL`  
**Production workbench:** `https://dcal-bm7i.vercel.app`  
**Implementation baseline before this documentation sync:** merge commit `3cb80fc9ffbe81472d32dd97fe7bc67e18440125` from PR #8  
**Current active milestone:** M1 — Secure ingestion and pilot

This document is the fastest way for a new AI/chat, developer, or reviewer to resume work without reconstructing context from prior conversations. It is a state snapshot, not a replacement for the normative architecture documents. If it conflicts with `ROADMAP.md`, `DECISIONS.md`, `ARCHITECTURE.md`, or `DATA_CONTRACT.md`, stop and resolve the conflict before changing implementation.

---

## 1. What DCAL is

DCAL means **Document Classification, Annotation, and Learning**. It is the standalone human-annotation and model-development laboratory for Bangladesh Medical College Hospital (BMCH) document pages.

The immediate product is a focused annotation workbench that lets a human:

1. identify the physical document type;
2. mark meaningful regions on the page;
3. classify those regions as fixed printed text, variable printed text, handwriting, choice/checkbox, table, or other meaningful content;
4. transcribe exact visible content;
5. preserve page provenance and revision history;
6. export only provenance-complete reviewed material into a stable gold-data contract.

DCAL is deliberately **not** an EMR/HMS, not DCRP, not the final clinical extraction engine, and not a model-serving gateway yet.

---

## 2. Non-negotiable system boundary

DCAL and DCRP are separate systems.

- Separate repositories.
- Separate deployments.
- Separate databases.
- Separate secrets.
- Separate release cycles.
- DCAL must not write directly into DCRP.
- Future DCRP integration is only through a promoted, versioned DCAL inference API after model-promotion gates are built and approved.

Machine output must never silently become human ground truth.

`unknown_document`, `unknown_region`, and `illegible` are valid labels. Do not force certainty.

Never commit patient images, PHI, real transcripts, source filenames, Drive IDs, signed URLs, exports, or credentials.

---

## 3. Current deployed state

### Hosted workbench

The first-party workbench is live on Vercel at:

`https://dcal-bm7i.vercel.app`

The deployed application is the Next.js app under `web/`. Vercel production tracks `main` and the project root is `web/`.

The application currently has:

- named Supabase email/password authentication;
- inactive-by-default membership;
- annotator / reviewer / admin roles;
- queue and status counts;
- pilot browser upload;
- private image delivery;
- physical document classification;
- template-variant selection;
- page-content profile selection;
- image-quality flags;
- box drawing, movement, resizing, reading order, field code, and legibility;
- exact transcription;
- multiline transcription;
- autosave;
- optimistic locking;
- append-only revision history;
- role-gated gold export;
- table-first structured transcription;
- trackpad-friendly image navigation.

The production deployment for PR #8 completed successfully and `/api/health` returned HTTP 200 after deployment.

### Supabase

A DCAL-only Supabase project exists and the repository migrations have been applied. The migrations are:

- `supabase/migrations/20260816040711_vercel_supabase_foundation.sql`
- `supabase/migrations/20260816041807_align_completion_exceptions.sql`

The hosted workbench uses Supabase for:

- Auth;
- `public.profiles` membership/roles;
- task operational state;
- append-only revisions;
- optimistic save functions;
- private `dcal-pages` working-copy storage.

Direct browser access to task/revision data is denied by policy; Next.js server routes mediate access with the server-only secret.

Do not put production secret values into documentation. Runtime variable names are in `web/.env.example` and `docs/DEPLOYMENT_RUNBOOK.md`.

### Google Drive ingestion

The Drive ingestion code is implemented and tested, including:

- dedicated Drive discovery;
- patient-folder / encounter-folder / file hierarchy validation;
- PDF/image rendering;
- 300-DPI RGB PNG normalization;
- raw and canonical page SHA-256 checksums;
- HMAC-derived opaque patient/encounter grouping;
- deduplication;
- quarantine;
- archive/content restriction;
- ingestion ledger;
- workbench signed-upload flow;
- idempotent task creation;
- cache rebuild and audit tooling.

**Important current-state distinction:** the code path exists, but this handoff does not assert that a production long-lived Drive worker is currently running. Verify that operational state before assuming dataset-ready ingestion is live.

Browser-uploaded pages are marked **Pilot upload** and are not gold-export eligible because they do not contain trustworthy patient/encounter grouping.

---

## 4. Current milestone and what remains

M1 is still active.

The hosted Vercel/Supabase foundation is operational. The remaining M1 work is primarily:

- continued usability refinement of the annotation interface;
- verify/operate the dedicated Drive ingestion worker for real dataset-ready pages;
- complete the human pilot;
- annotate approximately 50 pages per confirmed physical type;
- record annotation time, unclear taxonomy choices, frequent corrections, save conflicts, and completion errors;
- verify security, backup, recovery, and access-review gates before expanding real clinical use.

Do **not** jump ahead into model training merely because the annotation UI works. M2 still needs frozen dataset releases and patient/writer-separated splits before a defensible training/evaluation process exists.

---

## 5. Most recent implementation: PR #8

PR #8, **“Add fast table entry and trackpad-friendly annotation navigation”**, was merged on 17 August 2026.

Why it was needed:

- investigation reports such as CBC/haematology pages contain relational row/column data;
- drawing one rectangle for every cell is too slow;
- flattening an entire table into one text blob destroys structure;
- trackpad navigation in the first workbench version felt uncomfortable because wheel gestures primarily zoomed rather than naturally moving the page;
- the right-hand inspector was awkward to scroll while annotating.

### Table tool

A new **Table** tool (`T`) lets the annotator draw one parent rectangle around the visible table. The selected region uses:

```json
{
  "label": "other_region",
  "structure_role": "table",
  "legibility": "not_applicable",
  "table_data": {
    "rows": 3,
    "columns": 4,
    "header_rows": 1,
    "column_labels": [
      "printed_static",
      "printed_variable",
      "printed_static",
      "printed_static"
    ],
    "cells": [
      ["Test", "Result", "Unit", "Reference"],
      ["White Blood Cells", "07.50", "10^9/L", "4.00 - 11.00"],
      ["Haemoglobin", "13.40", "g/dL", "13 - 18"]
    ]
  }
}
```

The workbench provides a spreadsheet-style editor in the right inspector.

Interaction:

- `Tab`: next cell;
- `Enter`: cell below;
- `Shift+Enter`: insert newline inside a cell;
- spreadsheet clipboard paste with tab/newline delimiters fills a block of cells;
- row/column controls can expand or shrink the grid;
- one optional header row is currently represented as `header_rows` and treated as fixed printed content;
- each non-header column has a default content class: Fixed, Variable, or Writing.

Validation limits:

- 1–100 rows;
- 1–12 columns;
- rectangular cell matrix required;
- `column_labels` must use textual region classes;
- max 10,000 characters per cell;
- max 100,000 table characters total;
- a table must contain at least one non-empty cell before page completion;
- `table_data` is rejected if `structure_role` is not `table`.

Existing non-table `dcal.annotation.v2` records remain valid. No Supabase schema migration was required because annotation JSON is stored as a structured payload.

### Navigation changes

The hosted UI now behaves as follows:

- normal two-finger trackpad / wheel movement pans the image;
- pinch or `Ctrl/Cmd + wheel` zooms around the pointer;
- explicit **Pan** tool (`P`) supports drag-to-pan;
- existing Space-drag and middle-button panning still work;
- selected-region controls are moved to the top of the independently scrolling inspector;
- inspector overscroll is isolated from the canvas;
- normal text transcription is larger, multiline, auto-growing, and preserves line breaks.

---

## 6. Important implementation detail: UX v2 is an enhancement layer

Do not miss this.

The original hosted client remains in:

- `web/public/app.js`

The newer table/navigation behavior is layered on top in:

- `web/public/ux-v2.js`
- `web/public/ux-v2.css`

`web/app/page.tsx` loads the base client first and the UX enhancement afterward.

The enhancement script intentionally wraps/replaces selected globally defined functions such as tool selection, region creation, and inspector rendering, and intercepts pointer/wheel events in capture phase.

This was chosen as a low-risk incremental change after the hosted workbench was already operational.

### Consequence for future agents

Do **not**:

- remove `ux-v2.js` because its behavior appears to duplicate `app.js`;
- reorder the scripts without testing;
- convert the enhancement to a new module in one blind cleanup;
- modify the base wheel handler without understanding the capture-phase override;
- assume the table editor is represented in the original markup.

A future cleanup may merge UX v2 into a more maintainable client architecture, but that should be a dedicated refactor with full behavior tests and no simultaneous feature changes.

---

## 7. Code map: where to change what

### Hosted workbench shell and markup

- `web/app/page.tsx` — authenticated page entry; loads markup and browser scripts.
- `web/lib/workbench-markup.ts` — queue/workbench HTML structure and base controls.
- `web/app/globals.css` — original application styling.
- `web/public/app.js` — original browser client state, canvas, annotation, queue, autosave.
- `web/public/ux-v2.js` — table editor, Pan/Table tools, improved navigation, enhanced inspector behavior.
- `web/public/ux-v2.css` — UX v2 styles.

### Hosted validation and domain contracts

- `web/lib/contracts.ts` — shared constants/taxonomy-derived contracts and blank annotation shape.
- `web/lib/validation.ts` — server-side annotation normalization/validation, including `table_data`.
- `web/data/taxonomy.json` — web-bundled taxonomy copy.

### Hosted task/data access

- `web/lib/auth.ts` — current-member and role logic.
- `web/lib/tasks.ts` — task data functions and operational persistence helpers.
- `web/lib/ingestion.ts` — hosted ingestion payload contract.
- `web/lib/supabase/server.ts` — server-side Supabase clients.

### Hosted API routes

- `web/app/api/tasks/route.ts`
- `web/app/api/tasks/[id]/route.ts`
- `web/app/api/tasks/[id]/image/route.ts`
- `web/app/api/uploads/route.ts`
- `web/app/api/ingestion/tasks/route.ts`
- `web/app/api/ingestion/upload-url/route.ts`
- `web/app/api/taxonomy/route.ts`
- `web/app/api/me/route.ts`
- `web/app/api/health/route.ts`

### Supabase

- `supabase/migrations/` — timestamped database/storage/functions/RLS migrations.
- `supabase/README.md` — migration notes.

### Canonical taxonomy

- `config/taxonomy/bmch-document-taxonomy.v1.json`
- `web/data/taxonomy.json`
- `config/label-studio/bmch-page-annotation.v1.xml` — compatibility aliases.

**Critical rule:** taxonomy changes often need all three to stay aligned. CI specifically checks alias parity. PR #8 initially failed CI because `table` was added to the repository/web taxonomy but not the Label Studio compatibility `structure_role` choices.

### Drive ingestion

- `src/dcal_ingestion/drive.py` — Drive operations.
- `src/dcal_ingestion/render.py` — deterministic page rendering.
- `src/dcal_ingestion/identity.py` — opaque identity derivation.
- `src/dcal_ingestion/ledger.py` — persistent ingestion ledger.
- `src/dcal_ingestion/service.py` — orchestration.
- `src/dcal_ingestion/workbench.py` — first-party workbench client.
- `src/dcal_ingestion/recovery.py` — audit/recovery.
- `src/dcal_ingestion/cli.py` — operational commands.

### Local compatibility workbench

- `src/dcal_workbench/`

This is still useful for local development/recovery compatibility, but the hosted Next.js workbench is the primary product path.

### Gold/legacy annotation tooling

- `src/dcal_annotations/`
- `config/label-studio/`

Label Studio is compatibility only; do not design new core behavior around its export format.

---

## 8. Annotation data model

The hosted mutable workbench uses `dcal.annotation.v2`.

Page-level fields:

- `schema_version`
- `document_type`
- `document_variant`
- `content_profile`
- `image_quality[]`
- `notes`
- `regions[]`

Core region fields:

- `id`
- `label`
- `structure_role`
- `legibility`
- `reading_order`
- `field_code`
- `transcription`
- `x`, `y`, `width`, `height`
- optional `table_data` only when `structure_role === "table"`

Coordinates are normalized page percentages so annotation geometry does not depend on rendered browser size.

Readable textual regions require exact transcription at completion. Do not normalize spelling or clinically infer what the text “must have meant.”

For a structured table, the cell matrix becomes the transcription source rather than the parent region's generic `transcription` string.

---

## 9. Physical-document taxonomy principles

DCAL separates:

1. physical document type;
2. physical document variant;
3. page content profile;
4. region content type;
5. optional semantic region meaning;
6. field/table structure.

Do not collapse these.

Examples:

- a Treatment Continuation Sheet is a physical page type but may contain follow-up notes, fresh orders, admission-context notes, or transfusion orders;
- a haematology report is a physical report type, while individual test-result values are variable table content;
- folder names are weak organizational context, not page ground truth;
- unknown/financial/blank/duplicate/non-clinical pages must remain valid physical outcomes.

The current taxonomy file lists the evidence-backed BMCH source classes.

---

## 10. Provenance and gold eligibility

There are two visually distinct task states.

### Pilot upload

Browser upload:

- useful for UI testing and taxonomy refinement;
- may contain normal annotations/revisions;
- does not contain trusted patient/encounter grouping;
- excluded from `dcal.gold.v1` export.

### Dataset-ready

Drive ingestion supplies:

- canonical rendered page hash;
- raw source hash;
- opaque source ID;
- opaque patient-group ID;
- opaque encounter-group ID;
- source page index;
- render profile;
- ingestion schema/key.

Only completed provenance-complete tasks may enter gold export.

A completed task is still not a frozen dataset release. M2 must create immutable releases/splits.

---

## 11. Security model

The major trust domains are deliberately separated:

- human Supabase session;
- server-only Supabase secret;
- Drive worker credential;
- ingestion bearer token;
- grouping HMAC key.

Rules:

- never expose `SUPABASE_SECRET_KEY` to browser code;
- never give annotators the ingestion token;
- never change the grouping HMAC key after ingestion begins without an explicit identity migration;
- never log request bodies containing clinical text or storage metadata;
- browser page storage is a private operational copy, not canonical storage;
- Google Drive remains canonical source/rendered-page archive for the pilot design;
- institutional approval, backup/restore, access review, retention, and incident response are still operational obligations even when the app builds successfully.

---

## 12. Verification before every change

A new AI should not trust only the documentation snapshot. First confirm current repository/deployment state.

Recommended sequence:

1. Inspect `main` HEAD and recent PRs.
2. Read `AGENTS.md`.
3. Read this file.
4. Read `ROADMAP.md`, `DECISIONS.md`, `ARCHITECTURE.md`, `DATA_CONTRACT.md`.
5. For UI changes, read `WORKBENCH_RUNBOOK.md`, `web/public/app.js`, `web/public/ux-v2.js`, and `web/app/page.tsx`.
6. For taxonomy changes, inspect canonical taxonomy, web taxonomy copy, Label Studio aliases, and `tests/test_configuration.py`.
7. For database changes, inspect every migration before writing a new one. Never edit an already-applied migration as if history had changed.
8. For hosted changes, verify the Vercel preview rather than assuming a successful local build is enough.

---

## 13. Required checks

### Root Python / contract suite

```bash
python -m unittest discover -s tests -v
```

### Hosted web app

```bash
cd web
npm ci
npm test
npm run typecheck
npm run build
```

### Docker / ingestion contract

When Docker is available:

```bash
docker compose config
docker compose --profile ingestion config
docker compose --profile ingestion build dcal-ingest
```

GitHub CI currently has two major jobs:

- `annotation-contract`
- `compose-contract`

Do not merge through a failing contract check merely because Vercel builds.

For Vercel changes, also verify:

- preview deployment is READY;
- build log has no actual errors;
- `/api/health` returns 200;
- production deployment is READY after merge.

---

## 14. Branch and PR workflow

Use one focused branch/PR per implementation block. Preferred branch prefix is:

`agent/<short-description>`

For user-authorized interactive development, it is acceptable for an AI with repository permission to open and merge its own focused PR **after** relevant CI and deployment checks pass. Do not merge through unresolved test failures, unknown migration state, or an unsafe clinical-data change.

Keep PR descriptions explicit about:

- what changed;
- why;
- data-contract impact;
- migration impact;
- security impact;
- checks run;
- known limitations.

---

## 15. Recent history worth knowing

The repository evolved quickly over 13–17 August 2026:

- Label Studio established the first annotation/taxonomy/export contract.
- Label Studio was superseded as the primary UI by the first-party workbench.
- Google Drive ingestion, deterministic rendering, checksum identity, grouping, deduplication, quarantine, audit, and recovery were implemented.
- A hosted Next.js/Supabase workbench was added.
- Supabase migrations established auth/profile/task/revision/storage/RLS/save foundations.
- Vercel deployment was corrected to use the `web/` Next.js application.
- The hosted pilot became operational.
- PR #8 added table-first investigation transcription and trackpad-friendly navigation.

The current task direction is still **human annotation usability and high-quality dataset creation**, not premature model integration.

---

## 16. Known technical debt / caution areas

### UX v2 layering

As described above, `ux-v2.js` monkey-patches/wraps the base workbench client. It is functional but not the ideal long-term architecture. Treat cleanup as a separate refactor.

### Duplicate taxonomy snapshots

The taxonomy exists in both canonical repo configuration and the web bundle. Keep them synchronized deliberately. Compatibility Label Studio aliases can also make CI fail if forgotten.

### Hosted vs local workbench divergence

The hosted UI is the primary path. The local Python workbench still exists and does not automatically inherit every hosted UX enhancement. Do not assume a frontend improvement in `web/` also exists in `src/dcal_workbench/static/`.

### Dataset release registry is not built

Operational completion is not equivalent to a training release. Do not create ad hoc “train/test” folders or silently split completed rows.

### Drive runtime state must be verified

Implementation exists, but a future agent should check whether the long-lived ingestion worker and dedicated Drive are currently active before making operational claims.

---

## 17. What the next chat is expected to do

The user intends to continue modifying the annotation platform after this documentation update.

For the next UI request:

- inspect the current production screenshot/behavior first;
- prefer small, testable workflow improvements over a rewrite;
- preserve annotation JSON compatibility unless a change genuinely requires a contract version bump;
- keep table entry fast;
- keep image movement and inspector scrolling comfortable;
- maintain exact visible-text principles;
- deploy through a focused PR and verify CI + Vercel.

Do not assume the next requested modification has already been specified in this document.

---

## 18. Normative reading order

For a fresh AI/chat, read in this order:

1. `AGENTS.md`
2. `docs/AI_HANDOFF.md`
3. `docs/ROADMAP.md`
4. `docs/DECISIONS.md`
5. `docs/ARCHITECTURE.md`
6. `docs/DATA_CONTRACT.md`
7. `docs/WORKBENCH_RUNBOOK.md`
8. `docs/TABLE_ENTRY_V2.md`
9. `docs/DEPLOYMENT_RUNBOOK.md` for hosted work
10. `docs/GOOGLE_DRIVE_RUNBOOK.md` for ingestion work
11. `docs/CHALLENGER_PLAYBOOK.md` and `docs/WINNING_COMPONENTS.md` only when entering model/experiment work
12. relevant implementation and tests

Then inspect current GitHub/Vercel state before changing anything.
