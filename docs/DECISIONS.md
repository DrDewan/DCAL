# Architecture decisions

## D-001 — DCAL is independent of DCRP

**Status:** Accepted, 13 August 2026

DCAL owns annotation and model development. It has no DCRP runtime or database dependency. Any future integration uses a promoted, versioned inference API.

## D-002 — Label Studio is the annotation workbench

**Status:** Accepted, 13 August 2026

Use self-hosted Label Studio Community for the pilot rather than building a custom canvas. DCAL owns the taxonomy and normalized output contract. Reassess Community versus self-hosted Enterprise after 500–1,000 real annotations using measured annotation time and review error.

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

## D-008 — No single “98% OCR” metric

**Status:** Accepted, 13 August 2026

Classification, character recognition, word recognition, exact-field extraction, critical-token errors, and accepted-result precision are evaluated separately. Static printed boilerplate may be supplied from a registered template and is not counted as newly recognized text.
