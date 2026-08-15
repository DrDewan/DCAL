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

The same rule applies to the first-party workbench: operational SQLite rows are mutable working state, while only a validated, frozen `dcal.gold.v1` release is training input.

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

The workbench and optional Label Studio adapter read checksum-addressed local files from a named volume. The volume is not canonical storage and can be reconstructed from the locked Drive page store. This avoids public Drive links and avoids giving annotator browsers Google credentials.

## D-012 — A first-party workbench is the primary annotation interface

**Status:** Accepted, 15 August 2026

DCAL owns a focused browser workbench for page queueing, document identification, content-profile classification, region boxes, exact transcription, completion, and revision history. The workbench writes repository-owned `dcal.annotation.v2` state and exports only provenance-complete, completed pages to `dcal.gold.v1`.

Browser upload is a convenience for synthetic tests and pilot annotation. It lacks patient/encounter grouping and is therefore visibly marked ineligible for dataset release. Dedicated Google Drive ingestion upgrades the same checksum-addressed page to dataset-eligible when complete opaque provenance arrives.

The private pilot binds to loopback by default. Internet or multi-user institutional deployment is blocked until an identity-aware reverse proxy, HTTPS, access logging, backups, session protection, and an institutional data-governance decision are in place.
