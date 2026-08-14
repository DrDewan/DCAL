# Locked implementation roadmap

The roadmap is milestone based. Only one implementation block is active at a time.

## M0 — Annotation foundation

**Status:** Code complete; operational usability gate pending

- Self-hosted Label Studio and PostgreSQL.
- Versioned BMCH taxonomy and single-page annotation configuration.
- Strict Label Studio export validation.
- Deterministic `dcal.gold.v1` normalization.
- Synthetic tests and CI.

**Exit gate:** configuration loads in Label Studio, synthetic export passes, malformed exports fail, and a human pilot confirms the controls are usable.

## M1 — Secure ingestion and pilot

**Status:** Active — implementation complete; dedicated Drive activation and pilot pending

- Dedicated Google Drive discovery and versioned folder bootstrap.
- Checksum-addressed source/page archive with Drive content restrictions and audit.
- Checksums, opaque patient/encounter grouping, and global page duplicate detection.
- Idempotent task creation through the Label Studio API.
- Rebuildable local annotation cache and persistent operational ledger.
- Pilot of 50 pages per confirmed physical type.
- Measured annotation time, disagreements, and taxonomy gaps.

**Exit gate:** no source/annotation identity gaps and pilot adjudication complete.

## M2 — Dataset registry and quality workflow

**Status:** Pending

- Versioned dataset releases.
- Patient- and writer-separated train/validation/sealed-test splits.
- Reviewer/adjudication workflow independent of Label Studio edition.
- Hidden gold tasks, annotator quality reports, and revision history.

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
