# DCAL annotation and gold-data contract v1

## Label Studio task input

Every task admitted to a gold dataset must contain:

```json
{
  "data": {
    "image": "private storage URI resolved by Label Studio",
    "source_object_id": "opaque immutable object ID",
    "source_sha256": "SHA-256 of the canonical rendered page PNG",
    "raw_source_sha256": "SHA-256 of the uploaded PDF or image",
    "patient_group_id": "keyed opaque grouping ID",
    "encounter_group_id": "keyed opaque grouping ID",
    "source_page_index": 1,
    "annotation_schema_version": "dcal.annotation.v1",
    "ingestion_schema_version": "dcal.ingestion.v1",
    "render_profile": "dcal.render.300dpi-rgb-png.v1",
    "dcal_ingestion_key": "task_<32 lowercase hex characters>"
  }
}
```

`patient_group_id` and `encounter_group_id` must be generated with a keyed HMAC or a secure random mapping. The Drive adapter HMACs stable patient-folder and encounter-folder IDs; it never exports their names or raw Drive IDs. A plain or unsalted hash of a hospital number is vulnerable to dictionary recovery and is forbidden.

The image URI is used only by Label Studio. The normalized gold record excludes ephemeral or signed URLs.

Ingestion provenance is an all-or-none bundle. Manually created legacy tasks may omit the whole bundle, but a task may not contain a partial raw hash, render profile, ingestion schema, or ingestion key. `source_sha256` identifies the exact page bytes used for annotation and model training. `raw_source_sha256` identifies the original uploaded object.

## Required page annotation

- Exactly one physical document type.
- Zero or one registered physical variant.
- Zero or more image-quality flags.
- Page notes are optional.

Clinical pages require at least one region. Blank, duplicate, cover, billing, and unknown pages may legitimately contain no OCR regions.

## Required region annotation

Every rectangle contains:

- one region label;
- normalized `x`, `y`, `width`, `height`, and rotation;
- positive unique reading order;
- one legibility state;
- zero or one semantic region type;
- exact verbatim transcription when required;
- zero or one stable field code.

Textual regions marked `legible` or `partially_legible` require transcription. `illegible` regions must have no invented transcript.

## Multiple human annotations

The adapter accepts:

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
    "label_studio_task_id": 1,
    "label_studio_annotation_id": 10,
    "annotator_id": 7,
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

The deterministic record hash detects accidental changes between dataset releases. It is not a digital signature and does not replace access control or release signing.

## Versioning

- Taxonomy changes create a new taxonomy version.
- Breaking normalized-output changes create a new `dcal.gold` version.
- Existing frozen dataset releases are never rewritten to look as if they were created under a newer schema.
