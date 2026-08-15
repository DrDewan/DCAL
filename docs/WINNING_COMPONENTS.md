# Winning components

This is the shared memory for reusable technical wins discovered by DCAL challengers.

Every challenger builder, including Claude, OpenAI, local OCR builders, and future agents, must read this document before proposing a new challenger. The point is not to crown one provider. The point is to accumulate components that can be recombined into better systems.

This file must never contain PHI, patient images, raw transcripts from real patients, Google Drive IDs, credentials, signed URLs, or any detail that can identify a patient or source folder.

## How to use this document

Add an entry when an experiment finds a reusable improvement, even if the whole challenger lost.

Examples of reusable components:

- preprocessing step
- page classification prompt pattern
- handwriting prompt pattern
- printed text OCR method
- layout segmentation method
- table extraction method
- post-processing or parser rule
- confidence calibration rule
- abstention/unknown handling rule
- document-type-specific template registration
- cost or latency optimization
- failure detector

Do not add vague observations. A future challenger builder should be able to implement or test the component from the entry.

## Entry template

```markdown
## WC-0000 — Short component name

- **Status:** candidate | adopted | rejected | superseded
- **Discovered by:** challenger ID, provider, commit SHA
- **Applies to:** document type, region type, model family, or pipeline stage
- **Component:** concise technical description
- **Evidence:** dataset release, metric movement, cost/latency impact
- **Failure modes:** where it failed or should not be used
- **How to reuse:** exact config, prompt fragment, parser rule, or implementation pointer
- **Follow-up:** next test or integration needed
```

## Promotion vocabulary

- **candidate:** useful but not yet part of the champion.
- **adopted:** incorporated into the champion or baseline challenger stack.
- **rejected:** tested and not worth reusing.
- **superseded:** replaced by a later component.

## Current baseline components

These are architectural components already established before M3 challenger work.

## WC-0001 — Separate DCAL laboratory boundary

- **Status:** adopted
- **Discovered by:** architecture decision, pre-challenger foundation
- **Applies to:** repository and deployment architecture
- **Component:** Keep DCAL independent from DCRP. DCAL owns annotation, dataset releases, experiments, and promotion. DCRP may later call only a promoted versioned inference API.
- **Evidence:** Reduces risk of experimental code writing into the clinical record platform. Allows challenger failures without DCRP regression.
- **Failure modes:** Adds integration work later; requires disciplined API/versioning before DCRP use.
- **How to reuse:** All challenger specs and experiment reports must declare DCAL contracts and must not depend on DCRP internals.
- **Follow-up:** Revisit only after M5 promotion gates pass.

## WC-0002 — Annotation UI state is not the canonical dataset

- **Status:** adopted
- **Discovered by:** M0 contract foundation; refined by M1 first-party workbench
- **Applies to:** annotation and dataset workflow
- **Component:** Use the first-party workbench for human annotation, then validate and normalize completed, provenance-eligible state into repository-owned `dcal.gold.v1` records. Retain Label Studio only as a compatibility adapter.
- **Evidence:** Protects DCAL from mutable UI/database state and export-shape drift, blocks provenance-incomplete browser uploads from gold export, and makes downstream challenger scoring stable.
- **Failure modes:** Requires adapter maintenance when annotation UI evolves.
- **How to reuse:** Challengers consume frozen normalized dataset releases, not workbench SQLite rows or raw Label Studio exports.
- **Follow-up:** M2 should add release registry and adjudication workflow.

## WC-0003 — Opaque grouped identity and immutable source checksums

- **Status:** adopted
- **Discovered by:** M1 ingestion foundation
- **Applies to:** ingestion, dataset lineage, scoring, and audit
- **Component:** Use SHA-256 for byte identity and keyed opaque HMAC IDs for patient and encounter grouping. Do not expose Drive names, IDs, or folder structure to the workbench, optional Label Studio adapter, or logs.
- **Evidence:** Preserves deduplication and lineage while reducing identifier leakage.
- **Failure modes:** Changing the HMAC key after ingestion breaks stable grouping unless an explicit migration is built.
- **How to reuse:** Challenger outputs should reference only normalized page/source IDs and dataset release IDs.
- **Follow-up:** Dataset registry should freeze identity mappings without exposing raw Drive metadata.

## WC-0004 — Static printed template text should be registered

- **Status:** adopted
- **Discovered by:** architecture baseline
- **Applies to:** printed forms and repeated BMCH boilerplate
- **Component:** Known static template text should come from registered templates where possible. Do not spend model budget repeatedly OCRing boilerplate and do not count static boilerplate as variable-text accuracy.
- **Evidence:** Prevents inflated OCR accuracy and focuses evaluation on variable printed/handwritten content.
- **Failure modes:** Template drift or photocopy variants can cause false assumptions if templates are not versioned.
- **How to reuse:** Challengers should separate template alignment/static text from variable content extraction.
- **Follow-up:** M3 should create template registration and template-drift checks.

## WC-0005 — Unknown and illegible are valid predictions

- **Status:** adopted
- **Discovered by:** M0/M1 safety baseline
- **Applies to:** classification, transcription, and field extraction
- **Component:** A challenger may return `unknown_document`, `unknown_region`, or `illegible` when evidence is insufficient.
- **Evidence:** Reduces false certainty, which is more dangerous than human review.
- **Failure modes:** Excessive abstention can make the system useless; track coverage and accepted-result precision together.
- **How to reuse:** Every challenger report must include abstention, false acceptance, and illegibility behavior.
- **Follow-up:** M4/M5 should calibrate thresholds for human review.

## Open slots

Add new reusable findings below this line as challengers run.
