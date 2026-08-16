# DCAL annotation and gold-data contract v1

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
    "annotation_schema_version": "dcal.annotation.v1",
    "ingestion_schema_version": "dcal.ingestion.v1",
    "render_profile": "dcal.render.300dpi-rgb-png.v1",
    "dcal_ingestion_key": "task_<32 lowercase hex characters>",
    "storage_path": "pages/<first two SHA-256 characters>/<SHA-256>.png",
    "image_width": 2480,
    "image_height": 3508
  }
}
```

`patient_group_id` and `encounter_group_id` must be generated with a keyed HMAC or a secure random mapping. The Drive adapter HMACs stable patient-folder and encounter-folder IDs; it never exports their names or raw Drive IDs. A plain or unsalted hash of a hospital number is vulnerable to dictionary recovery and is forbidden.

The legacy `image` URI is used only by the local/Label Studio compatibility path. The deployed workbench uploads the rendered bytes through a short-lived signed upload URL, then stores the checksum-derived private Supabase Storage path. The normalized gold record excludes paths, ephemeral URLs, and signed URLs.

Ingestion provenance is an all-or-none bundle. Manually created legacy tasks may omit the whole bundle, but a task may not contain a partial raw hash, render profile, ingestion schema, or ingestion key. `source_sha256` identifies the exact page bytes used for annotation and model training. `raw_source_sha256` identifies the original uploaded object.

## Workbench annotation state

The first-party workbench stores mutable `dcal.annotation.v2` working state:

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

`content_profile` separates a blank printed form, a printed form with typed values, a fully printed document, a printed form with handwriting, a primarily handwritten page, and an unknown profile. This is independent of the physical document type.

Each successful save increments an integer version and appends a revision containing the annotator display name, action, normalized annotation JSON, and timestamp. The update is rejected when the submitted expected version is stale. Revision history is operational evidence; it is not itself a frozen dataset release.

## Required page annotation

- Exactly one physical document type.
- Zero or one registered physical variant belonging to the selected type.
- Exactly one content profile before completion.
- Zero or more image-quality flags.
- Page notes are optional.

Clinical pages, including financial/billing documents, require at least one region. Blank, duplicate, non-clinical cover, and unknown pages may legitimately contain no OCR regions.

## Required region annotation

Every workbench rectangle contains:

- one region label;
- normalized `x`, `y`, `width`, `height`, and rotation;
- positive unique reading order;
- one legibility state;
- exact verbatim transcription when required;
- zero or one stable field code.

Textual regions marked `legible` or `partially_legible` require transcription. `illegible` regions must have no invented transcript.

## Dataset eligibility

Browser-uploaded pilot pages lack trustworthy patient and encounter grouping. They may be annotated and revisioned but are excluded from `dcal.gold.v1` export. When the Drive ingester later submits the same canonical page checksum or exact raw-image checksum with complete opaque provenance, the existing task is upgraded to dataset-eligible without discarding its annotation. Client-resized browser images may not match and should be treated as UI pilots only.

Completed pages remain working state until a later dataset-registry milestone freezes them into a versioned, split manifest. A completed row is not automatically a training release.

## Legacy Label Studio annotations

The Label Studio compatibility adapter accepts:

- one active annotation; or
- multiple active annotations when exactly one is explicitly marked `ground_truth`.

Any other multiplicity is rejected for adjudication. The adapter never selects the newest annotation silently.

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

For a legacy Label Studio export, the annotation object retains `label_studio_task_id`, `label_studio_annotation_id`, and `annotator_id`. Consumers must accept the source-specific provenance object while treating the remaining `dcal.gold.v1` fields identically.

The deterministic record hash detects accidental changes between dataset releases. It is not a digital signature and does not replace access control or release signing.

## Versioning

- Taxonomy changes create a new taxonomy version.
- Breaking normalized-output changes create a new `dcal.gold` version.
- Existing frozen dataset releases are never rewritten to look as if they were created under a newer schema.
