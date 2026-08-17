# DCAL annotation and gold-data contract v1

Read `AI_HANDOFF.md` for the current deployed implementation snapshot. This document defines the data-contract rules.

## Ingestion task input

Every workbench task admitted to a gold dataset must originate from an ingestion payload containing:

```json
{
  "data": {
    "image": "private checksum-addressed cache URI resolved by DCAL",
    "source_object_id": "opaque immutable object ID",
    "source_sha256": "SHA-256 of the canonical rendered page PNG",
    "raw_source_sha256": "SHA-256 of the uploaded PDF or image",
    "patient_group_id": "keyed opaque grouping ID",
    "encounter_group_id": "keyed opaque grouping ID",
    "source_page_index": 1,
    "annotation_schema_version": "dcal.annotation.v2",
    "ingestion_schema_version": "dcal.ingestion.v1",
    "render_profile": "dcal.render.300dpi-rgb-png.v1",
    "dcal_ingestion_key": "task_<32 lowercase hex characters>",
    "storage_path": "pages/<first two SHA-256 characters>/<SHA-256>.png",
    "image_width": 2480,
    "image_height": 3508
  }
}
```

`patient_group_id` and `encounter_group_id` must be generated with a keyed HMAC or secure random mapping. The Drive adapter HMACs stable patient-folder and encounter-folder IDs and never exports names or raw Drive IDs. A plain/unsalted hash of a hospital number is forbidden.

The legacy `image` URI is used only by local/Label Studio compatibility paths. The deployed workbench uploads rendered bytes through a short-lived signed upload URL and stores the checksum-derived private Supabase Storage path. Normalized gold records exclude storage paths, ephemeral URLs, and signed URLs.

Ingestion provenance is an all-or-none bundle. Manually created legacy tasks may omit the whole bundle, but a task may not contain partial raw hash/render profile/ingestion schema/key provenance. `source_sha256` identifies exact page bytes used for annotation/training. `raw_source_sha256` identifies the original uploaded object.

## Workbench annotation state

The first-party workbench stores mutable `dcal.annotation.v2` state:

```json
{
  "schema_version": "dcal.annotation.v2",
  "document_type": "bmch_admission_form",
  "document_variant": "bmch_admission_form_v1",
  "content_profile": "printed_blank_form",
  "image_quality": ["clear"],
  "notes": "",
  "regions": []
}
```

`content_profile` separates blank printed forms, forms with typed values, fully printed documents, printed forms with handwriting, primarily handwritten pages, and unknown profile. This is independent of physical document type.

Each successful save increments an integer version and appends a revision containing annotator display name, action, normalized annotation JSON, and timestamp. Updates are rejected when expected version is stale. Revision history is operational evidence, not a frozen dataset release.

## Required page annotation

- Exactly one physical document type.
- Zero or one registered physical variant belonging to that type.
- Exactly one content profile before completion.
- Zero or more image-quality flags.
- Page notes optional.

Clinical pages, including financial/billing documents, require at least one region. Blank, duplicate, non-clinical cover, and unknown pages may contain no OCR regions.

## Required region annotation

Every workbench rectangle contains:

- one region label;
- normalized `x`, `y`, `width`, `height` geometry;
- positive unique reading order;
- one legibility state;
- exact verbatim transcription when required;
- zero or one stable field code;
- one structure role;
- optional `table_data` only when `structure_role` is `table`.

Example ordinary textual region:

```json
{
  "id": "reg_0123456789ab",
  "label": "printed_variable",
  "structure_role": "form_field",
  "legibility": "legible",
  "reading_order": 1,
  "field_code": "patient_name",
  "transcription": "SHAHRIAR ZAMAN",
  "table_data": null,
  "x": 12.1,
  "y": 18.4,
  "width": 31.0,
  "height": 3.2
}
```

Textual regions marked `legible` or `partially_legible` require transcription at completion. `illegible` regions must not contain an invented transcript.

Line breaks in `transcription` are meaningful visible structure and are preserved.

## Structured table region

Investigation reports and charts may be represented as one parent region rather than one rectangle per cell.

The parent region uses:

- `label: "other_region"`;
- `structure_role: "table"`;
- `legibility: "not_applicable"`;
- optional stable `field_code` for the whole table;
- structured `table_data`.

Example:

```json
{
  "id": "reg_abcdef012345",
  "label": "other_region",
  "structure_role": "table",
  "legibility": "not_applicable",
  "reading_order": 4,
  "field_code": "cbc_results",
  "transcription": "",
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
  },
  "x": 8.0,
  "y": 31.0,
  "width": 84.0,
  "height": 52.0
}
```

### `table_data` fields

- `rows`: integer, 1–100.
- `columns`: integer, 1–12.
- `header_rows`: integer, 0–`rows`.
- `column_labels`: exactly one textual region label per column. Current workbench UI exposes Fixed (`printed_static`), Variable (`printed_variable`), and Writing (`handwriting`).
- `cells`: rectangular string matrix with exactly `rows` rows and `columns` cells per row.

Validation limits:

- each cell max 10,000 characters;
- total table text max 100,000 characters;
- a completed table must contain at least one non-empty cell;
- table column labels must map to taxonomy labels marked textual;
- `table_data` must be absent/null for non-table regions.

Header rows are treated as fixed printed content by the current workbench UI. `column_labels` describe default non-header cell content class.

The table cell matrix is the structured transcription source. Do not flatten the entire table into the parent region `transcription` field.

## Dataset eligibility

Browser-uploaded pilot pages lack trustworthy patient/encounter grouping. They may be annotated/revisioned but are excluded from `dcal.gold.v1` export.

When Drive ingestion later submits the same canonical page checksum or exact raw-image checksum with complete opaque provenance, the existing task may be upgraded to dataset-eligible without discarding annotation. Client-resized browser images may not match and should be treated as UI pilots only.

Completed pages remain working state until a later dataset-registry milestone freezes them into a versioned split manifest. A completed row is not automatically a training release.

## Legacy Label Studio annotations

The Label Studio compatibility adapter accepts:

- one active annotation; or
- multiple active annotations when exactly one is explicitly marked `ground_truth`.

Any other multiplicity is rejected for adjudication. The adapter never silently selects the newest annotation.

Label Studio compatibility does not define the permanent hosted workbench schema. New hosted-only structures such as `table_data` must remain repository-owned contracts rather than Label Studio-specific export inventions.

## Normalized output

One JSON object is written per page in JSONL format:

```json
{
  "schema_version": "dcal.gold.v1",
  "taxonomy_version": "dcal.taxonomy.v1",
  "source": {
    "object_id": "opaque-source-001",
    "sha256": "...",
    "patient_group_id": "patient-group-001",
    "encounter_group_id": "encounter-group-001",
    "page_index": 1,
    "ingestion": {
      "raw_sha256": "...",
      "schema_version": "dcal.ingestion.v1",
      "render_profile": "dcal.render.300dpi-rgb-png.v1",
      "task_key": "task_..."
    }
  },
  "annotation": {
    "source": "dcal_workbench",
    "workbench_task_id": "page_000001",
    "annotator": "Team display name",
    "created_at": "...",
    "updated_at": "..."
  },
  "classification": {
    "physical_document_type": "bmch_admission_form",
    "physical_document_variant": "bmch_admission_form_v1"
  },
  "image_quality": ["clear"],
  "regions": [],
  "record_sha256": "deterministic hash of the record before this field"
}
```

For legacy Label Studio export, the annotation object retains Label Studio-specific provenance IDs. Consumers accept source-specific annotation provenance while treating the remaining `dcal.gold.v1` fields identically.

The deterministic record hash detects accidental changes between dataset releases. It is not a digital signature and does not replace access control/release signing.

## Versioning

- Taxonomy changes create a new taxonomy version when semantics break existing interpretation.
- Breaking annotation-state changes require a new `dcal.annotation` version.
- Additive optional fields that remain backward-compatible may stay within `dcal.annotation.v2` when explicitly documented and validated.
- Breaking normalized-output changes create a new `dcal.gold` version.
- Existing frozen dataset releases are never rewritten to appear as if they were created under a newer schema.
