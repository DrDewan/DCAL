# Locked implementation roadmap

The roadmap is milestone based. Only one implementation block is active at a time.

For the current deployed implementation snapshot and exact continuation context, read `docs/AI_HANDOFF.md` before making changes.

## M0 — Annotation foundation

**Status:** Superseded foundation retained for compatibility

- Optional self-hosted Label Studio and PostgreSQL compatibility stack.
- Versioned BMCH taxonomy and single-page annotation configuration.
- Strict Label Studio export validation.
- Deterministic `dcal.gold.v1` normalization.
- Synthetic tests and CI.

**Exit gate:** historical contract complete; the usability gate moved to M1 under the first-party workbench.

## M1 — Secure ingestion and pilot

**Status:** Active — hosted Vercel/Supabase workbench is live; usability refinement and dataset-ready Drive pilot remain active

Implemented:

- First-party annotation workbench with page queue, progress, upload, document/content identification, typed boxes, transcription, autosave, optimistic locking, and revision history.
- Named Supabase authentication with inactive-by-default membership and annotator/reviewer/admin roles.
- Private page delivery and server-mediated task/revision access.
- Dedicated Google Drive discovery and versioned folder bootstrap.
- Checksum-addressed source/page archive design with Drive content restrictions and audit.
- Checksums, opaque patient/encounter grouping, and global page duplicate detection.
- Idempotent task creation through the private workbench API.
- Rebuildable local annotation cache and persistent operational ledger.
- Deterministic gold export that excludes provenance-incomplete browser uploads.
- DCAL-only Supabase schema, append-only revisions, optimistic-locking functions, RLS deny policies, and migration history.
- Table-first structured annotation for investigation reports and charts using one parent region plus a spreadsheet-like `table_data` cell matrix.
- Trackpad-friendly image navigation: wheel/trackpad pan, pointer-centred pinch/Ctrl/Cmd-wheel zoom, explicit Pan tool, and independent inspector scrolling.
- Production Vercel deployment at `https://dcal-bm7i.vercel.app`.

Still required before M1 exit:

- Continue human-centered usability refinement based on real annotation sessions.
- Verify and operate the production long-lived Google Drive ingestion worker before assuming dataset-ready ingestion is live.
- Complete the pilot of approximately 50 pages per confirmed physical type.
- Measure annotation time, disagreement patterns, taxonomy gaps, frequent geometry corrections, save conflicts, and completion errors.
- Complete/verify production backup, recovery, access-review, retention, and incident-response gates for real clinical material.
- Resolve any annotation-contract gaps discovered during the pilot through explicit versioned changes rather than informal fields.

**Exit gate:** private deployment security/recovery is approved, no source/annotation identity gaps remain, the Drive path is operational for dataset-ready pages, and a human pilot confirms that document identification, box/table annotation, transcription, navigation, autosave, and completion are practical at scale.

## M2 — Dataset registry and quality workflow

**Status:** Pending; do not treat completed M1 rows as a frozen training release

- Versioned dataset releases.
- Patient- and writer-separated train/validation/sealed-test splits.
- Reviewer/adjudication workflow in the first-party workbench.
- Hidden gold tasks, annotator quality reports, and revision history.
- Immutable release manifests and release-level provenance.

## M3 — Baseline classification and printed text

**Status:** Pending

- Image preprocessing and template alignment baselines.
- Classifier challengers with explicit unknown handling.
- Printed variable-text OCR and static-template registration.
- RunPod/CPU adapters behind common experiment contracts.
- Provider-neutral challenger specs for OpenAI, Claude, local OCR, and hybrid runners.
- Shared winning-components workflow so reusable discoveries can be combined across challengers.

## M4 — Handwriting and structured extraction

**Status:** Pending

- Line-level handwriting benchmarks.
- Specialist OCR/VLM challengers.
- Field and table extraction by physical type/variant.
- Critical-token error analysis and uncertainty calibration.
- Claude and other VLM challengers evaluated only through frozen snapshots and normalized prediction contracts.

## M5 — Champion promotion and inference gateway

**Status:** Pending

- Immutable model/config/container registry.
- Champion-versus-challenger gates.
- Versioned inference API, observability, retry, and rollback.

## M6 — Optional DCRP adapter

**Status:** Blocked until M5 gates pass and explicitly authorized

- DCRP calls a promoted DCAL API.
- Machine results remain drafts with provenance and confidence.
- Human confirmation and existing DCRP review invariants remain intact.
