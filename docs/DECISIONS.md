# Architecture decisions

## D-001 — DCAL is independent of DCRP

**Status:** Accepted, 13 August 2026

DCAL owns annotation and model development. It has no DCRP runtime or database dependency. Any future integration uses a promoted, versioned inference API.

## D-002 — Label Studio is the annotation workbench

**Status:** Superseded by D-012, 15 August 2026

Label Studio established the first annotation contract and remains a compatibility adapter. The first-party workbench now replaces it as the primary pilot interface because DCAL requires a narrower, form-focused workflow: identify the page, draw typed boxes, and transcribe each box.

## D-003 — The annotation unit is one page image

**Status:** Accepted, 13 August 2026

Multi-page source order is retained in metadata, but classification, geometry, transcription, training, and evaluation operate on immutable single-page images.

## D-004 — Physical type is separate from semantic content

**Status:** Accepted, 13 August 2026

A Treatment Continuation Sheet can carry follow-up, orders, admission context, or transfusion instructions. The page classifier labels the physical page; semantic regions are labelled separately.

## D-005 — Abstention is correct behavior

**Status:** Accepted, 13 August 2026

Unknown pages, unknown regions, and illegible text are valid ground-truth outcomes. Neither annotators nor models may be forced to guess.

## D-006 — Dataset identity is content based

**Status:** Accepted, 13 August 2026

Every source page is identified by byte-level SHA-256 plus an opaque object ID. Patient and encounter grouping use keyed opaque identifiers so the same groups can be kept within one split without storing raw hospital identifiers.

## D-007 — Label Studio export is an adapter input

**Status:** Accepted, 13 August 2026

The permanent dataset format is `dcal.gold.v1`. Label Studio JSON is validated and normalized deterministically; it is not used directly for training.

The same rule applies to the first-party workbench: operational SQLite or Supabase rows are mutable working state, while only a validated, frozen `dcal.gold.v1` release is training input.

## D-008 — No single “98% OCR” metric

**Status:** Accepted, 13 August 2026

Classification, character recognition, word recognition, exact-field extraction, critical-token errors, and accepted-result precision are evaluated separately. Static printed boilerplate may be supplied from a registered template and is not counted as newly recognized text.

## D-009 — A dedicated Google Drive is the pilot source and page store

**Status:** Accepted, 14 August 2026

Use a DCAL-only Google Drive or Google Workspace Shared Drive for intake, processed originals, rendered pages, quarantine, and future dataset exports. Prefer a Shared Drive with a service account; use a dedicated-account OAuth credential when Workspace is unavailable. Do not mix DCAL clinical files with a personal or general institutional Drive.

Drive content restrictions, checksums, and audits reduce accidental mutation but do not provide true write-once retention. A future compliance requirement may force migration to object-lock storage without changing the gold-data contract.

## D-010 — Patient grouping comes from folder identity, not folder names

**Status:** Accepted, 14 August 2026

The inbox hierarchy is patient folder, then encounter folder, then source files. DCAL HMACs stable Drive folder IDs and never exports the names or raw IDs. Incorrect folder depth is rejected because silently assigning synthetic one-page patients would invalidate patient-separated evaluation.

## D-011 — Annotation media is a rebuildable cache

**Status:** Accepted, 14 August 2026

The local workbench and optional Label Studio adapter read checksum-addressed local files from a named volume. The deployed workbench reads a private checksum-addressed working copy from Supabase Storage through authenticated server routes. Neither working copy is canonical storage; Google Drive remains the source and rendered-page archive. Annotator browsers never receive Google credentials.

## D-012 — A first-party workbench is the primary annotation interface

**Status:** Accepted, 15 August 2026

DCAL owns a focused browser workbench for page queueing, document identification, content-profile classification, region boxes, exact transcription, completion, and revision history. The workbench writes repository-owned `dcal.annotation.v2` state and exports only provenance-complete, completed pages to `dcal.gold.v1`.

Browser upload is a convenience for synthetic tests and pilot annotation. It lacks patient/encounter grouping and is therefore visibly marked ineligible for dataset release. Dedicated Google Drive ingestion upgrades an exact canonical-page or raw-image match to dataset-eligible when complete opaque provenance arrives.

The local compatibility pilot binds to loopback by default. D-013 defines the authenticated hosted pilot. Institutional data-governance approval, tested backups, access review, and incident procedures remain deployment gates before real clinical material is admitted.

## D-013 — The hosted pilot uses Vercel plus a separate Supabase project

**Status:** Accepted, 16 August 2026

The hosted annotation workbench is a Next.js application deployed independently on Vercel. A DCAL-only Supabase project provides named email/password authentication, mutable PostgreSQL task/revision state, and a private working-copy page bucket. The dedicated Google Drive remains the canonical intake, original archive, and rendered-page archive.

The browser receives only a Supabase publishable key and session cookies. It has no direct task, revision, page-object, Google Drive, or secret-key access. Authenticated Vercel route handlers revalidate the user, read role and activation state from `public.profiles`, and use a server-only Supabase secret key. Direct Data API policies deny browser roles access to tasks and revisions. Gold export is limited to reviewer and admin roles.

New Auth users are inactive annotators until an administrator explicitly activates them. Public signup is disabled. The Drive worker authenticates separately with a high-entropy ingestion bearer token, receives short-lived signed upload URLs for rendered PNGs, and never receives the Supabase secret key.

Browser upload remains pilot-only, accepts JPEG/PNG/WebP images, and cannot create dataset grouping. PDF and canonical dataset ingestion run on the separate long-lived Drive worker, not inside Vercel functions. Supabase free-tier capacity is suitable only for a small pilot; storage usage must be monitored and upgraded before it becomes a dataset bottleneck.

## D-014 — Relational tables are annotated as one parent region plus structured cells

**Status:** Accepted, 17 August 2026

Investigation reports and hospital charts frequently contain relational tables. DCAL will not require a human annotator to draw and transcribe every visible cell as an independent rectangle when the relational grid is the meaningful unit.

A table is represented by one page-coordinate parent region with `structure_role: "table"` and an additive structured `table_data` payload containing row count, column count, header-row count, default textual content class per column, and a rectangular cell string matrix.

This preserves both geometry and row/column relationships while keeping the initial human workflow fast enough for dataset production. The parent region remains an ordinary `dcal.annotation.v2` region; the additive table payload does not require a Supabase schema migration and does not invalidate existing non-table annotations.

Current table limits are deliberately bounded: at most 100 rows, 12 columns, 10,000 characters per cell, and 100,000 table characters total. Completed tables require at least one non-empty cell.

The hosted workbench exposes Fixed, Variable, and Writing as default non-header column classes. Header rows are currently treated as fixed printed content.

Do not flatten a structured table into a single generic transcription string. Do not multiply table cells into independent rectangles solely to imitate OCR training data; downstream extraction representations can be derived later from the structured gold annotation.

## D-015 — Human annotation ergonomics are a first-class M1 constraint

**Status:** Accepted, 17 August 2026

The purpose of M1 is to create reliable human-reviewed data at usable speed. Annotation ergonomics therefore affect dataset quality and throughput and are not cosmetic-only concerns.

The hosted canvas uses ordinary wheel/two-finger gestures to pan the page, pinch or `Ctrl/Cmd + wheel` to zoom around the pointer, and an explicit Pan tool for drag movement. The selected-region editor scrolls independently from the canvas and multiline transcription preserves visible line breaks.

The current implementation delivers these changes through a `ux-v2.js` enhancement layer loaded after the base `app.js`. This layering is an implementation compromise, not a permanent architectural requirement. A future consolidation must be a dedicated behavior-preserving refactor rather than an incidental cleanup bundled with new annotation features.

## D-016 — Structured table cells are part of normalized output, as `dcal.gold.v2`

**Status:** Accepted, 17 August 2026

D-014 made `table_data` the structured transcription source for relational tables, and `DATA_CONTRACT.md` forbids flattening a table into the parent region `transcription`. Both normalizers nevertheless dropped `table_data` when building normalized records, so every transcribed investigation table was discarded at the export boundary and no gold consumer could see table content in any form.

Normalized region output now carries `table_data`: the structured payload for `structure_role: "table"` regions, and an explicit `null` for every other region and for every legacy Label Studio record. Both the hosted exporter and the local compatibility exporter emit the same region shape.

This is a new `dcal.gold` version rather than an additive change within v1. The additive-field allowance in `DATA_CONTRACT.md` covers mutable `dcal.annotation` state, where no record hash is published. Normalized output includes `record_sha256` over the whole record, so adding a region field changes the hash of every exported page. Reusing `dcal.gold.v1` would have produced two different hashes under one version string and defeated the purpose of the hash. No frozen release exists yet, so the migration cost of the bump is zero and the ambiguity cost of not bumping is permanent.

`dcal.gold.v1` was never produced by a working hosted export path, so no v1 artifact needs migration. The local compatibility exporter and the Label Studio adapter both move to v2 together, keeping one shape across sources as required by `DATA_CONTRACT.md`.

## D-017 — The hosted workbench is covered by CI

**Status:** Accepted, 17 August 2026

Until this decision, GitHub CI validated the Python annotation and Compose/ingestion contracts only. The hosted Next.js application — the sole production annotation interface — had tests, a typecheck, and a build that no automated check ever ran, and the missing gold-export route that D-013 required reached production undetected as a result.

CI now runs a `hosted-workbench` job on every pull request: dependency install, `npm test`, `npm run typecheck`, `node --check` on both `public/app.js` and `public/ux-v2.js`, and a production `npm run build`. The build uses shape-valid placeholder environment values so `lib/env.ts` validation runs without contacting Supabase; real values remain only in Vercel project settings.

The browser-client syntax check covers `ux-v2.js` as well as the base client because the UX v2 layer is loaded on every hosted page and a syntax error there silently disables table entry and navigation rather than failing the build.

## D-018 — Annotation is implemented once, in the hosted workbench

**Status:** Accepted, 17 August 2026

D-012 made the first-party workbench the primary annotation interface and D-013 moved it to Vercel plus Supabase, but the original local Python workbench kept its own full annotation implementation: a second validator, a second save path with its own optimistic locking, a second gold exporter, and a second browser client. One contract, two implementations, in two languages.

They drifted, as duplicated contracts do. The Python validator silently discarded `table_data` on save while declaring the same `dcal.annotation.v2` schema string as the hosted validator that preserved it, so the same payload meant different things depending on which implementation received it.

`src/dcal_workbench/` is therefore reduced to an ingestion sink and upload renderer. It keeps `import_ingestion_task`, `upload_sources`, the task index, and read-only task/image inspection. It loses the annotation validator, `save_task`, `export_gold`, the `revisions` table, the taxonomy dependency, the `/api/taxonomy` and gold-export endpoints, the `PUT` handler, and the entire `static/` browser client.

It is retained rather than deleted because it renders PDF, TIFF, and BMP sources at 300 DPI, which the hosted upload route deliberately cannot do: D-013 keeps PDF rendering off Vercel functions, and `web/app/api/uploads/route.ts` accepts only JPEG/PNG/WebP under 4 MiB.

The local service is not an alternative annotation path, and pages ingested locally are not annotatable until they also reach the hosted workbench. A laptop-side upload cannot be made dataset-eligible: `tasks_provenance_bundle` requires `google_drive` origin with patient and encounter grouping, so files that belong in the dataset go into the Drive inbox and acquire real provenance from the worker. Do not add a local annotation UI back, and do not manufacture grouping identifiers to make a local upload look dataset-ready.

Consequence to accept deliberately: `web/lib/validation.ts` is now the only annotation validator and has no second implementation to disagree with it. That is the point, but it means its own tests are the only guard, which is why D-017 put them in CI first.
