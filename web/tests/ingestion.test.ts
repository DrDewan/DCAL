import assert from "node:assert/strict";
import test from "node:test";

import { canonicalPagePath, taskIngestionKey, validateIngestionTask } from "@/lib/ingestion";
import { HttpError } from "@/lib/http";

test("ingestion identity and storage path are content addressed", () => {
  const sha256 = "a".repeat(64);
  assert.equal(canonicalPagePath(sha256), `pages/aa/${sha256}.png`);
  assert.match(taskIngestionKey(sha256), /^task_[0-9a-f]{32}$/);
});

test("ingestion validates the full private provenance bundle", () => {
  const sha256 = "a".repeat(64);
  const result = validateIngestionTask({
    source_object_id: `src_${"A".repeat(32)}`,
    source_sha256: sha256,
    raw_source_sha256: "b".repeat(64),
    patient_group_id: `pat_${"B".repeat(32)}`,
    encounter_group_id: `enc_${"C".repeat(32)}`,
    writer_group_ids: [],
    source_page_index: 1,
    annotation_schema_version: "dcal.annotation.v1",
    ingestion_schema_version: "dcal.ingestion.v1",
    render_profile: "dcal.render.300dpi-rgb-png.v1",
    dcal_ingestion_key: taskIngestionKey(sha256),
    storage_path: canonicalPagePath(sha256),
    image_width: 1800,
    image_height: 2400,
  });
  assert.equal(result.imageWidth, 1800);
  assert.equal(result.patientGroupId.slice(0, 4), "pat_");
});

test("ingestion rejects a page path that does not match its checksum", () => {
  const sha256 = "a".repeat(64);
  assert.throws(() => validateIngestionTask({
    source_object_id: `src_${"A".repeat(32)}`,
    source_sha256: sha256,
    raw_source_sha256: "b".repeat(64),
    patient_group_id: `pat_${"B".repeat(32)}`,
    encounter_group_id: `enc_${"C".repeat(32)}`,
    writer_group_ids: [],
    source_page_index: 1,
    annotation_schema_version: "dcal.annotation.v1",
    ingestion_schema_version: "dcal.ingestion.v1",
    render_profile: "dcal.render.300dpi-rgb-png.v1",
    dcal_ingestion_key: taskIngestionKey(sha256),
    storage_path: "pages/ff/not-the-page.png",
    image_width: 1800,
    image_height: 2400,
  }), HttpError);
});
