import assert from "node:assert/strict";
import test from "node:test";

import { GOLD_SCHEMA } from "@/lib/contracts";
import { goldRecord, stableJson, type TaskRow } from "@/lib/tasks";

function datasetEligibleRow(): TaskRow {
  return {
    id: 1,
    ingestion_key: `task_${"a".repeat(32)}`,
    source_origin: "google_drive",
    dataset_eligible: true,
    source_object_id: "src_synthetic000000000000",
    source_sha256: "b".repeat(64),
    raw_source_sha256: "c".repeat(64),
    patient_group_id: "pat_synthetic000000000000",
    encounter_group_id: "enc_synthetic000000000000",
    writer_group_ids: [],
    source_page_index: 1,
    ingestion_schema_version: "dcal.ingestion.v1",
    render_profile: "dcal.render.300dpi-rgb-png.v1",
    storage_bucket: "dcal-pages",
    storage_path: `pages/bb/${"b".repeat(64)}.png`,
    image_width: 2480,
    image_height: 3508,
    status: "completed",
    assigned_to: null,
    assigned_to_name: "Synthetic Annotator",
    annotation: {
      schema_version: "dcal.annotation.v2",
      document_type: "bmch_haematology_report",
      document_variant: null,
      content_profile: "printed_filled_form",
      image_quality: ["clear"],
      notes: "",
      regions: [
        {
          id: "reg_abcdef012345",
          label: "other_region",
          structure_role: "table",
          legibility: "not_applicable",
          reading_order: 1,
          field_code: "cbc_results",
          transcription: "",
          table_data: {
            rows: 2,
            columns: 2,
            header_rows: 1,
            column_labels: ["printed_static", "printed_variable"],
            cells: [
              ["Test", "Result"],
              ["Haemoglobin", "13.40"],
            ],
          },
          x: 8,
          y: 31,
          width: 84,
          height: 52,
        },
      ],
    },
    version: 2,
    created_at: "2026-08-17T00:00:00.000Z",
    updated_at: "2026-08-17T00:05:00.000Z",
    completed_at: "2026-08-17T00:05:00.000Z",
  };
}

test("a gold record declares the current gold schema", () => {
  const record = goldRecord(datasetEligibleRow());
  assert.equal(record.schema_version, GOLD_SCHEMA);
  assert.equal(GOLD_SCHEMA, "dcal.gold.v2");
});

test("structured table cells survive gold export", () => {
  const record = goldRecord(datasetEligibleRow());
  const regions = record.regions as Record<string, unknown>[];
  const tableData = regions[0].table_data as { cells: string[][] } | null;
  assert.ok(tableData, "table_data must be present in the exported region");
  assert.deepEqual(tableData.cells, [
    ["Test", "Result"],
    ["Haemoglobin", "13.40"],
  ]);
});

test("a non-table region exports an explicit null table payload", () => {
  const row = datasetEligibleRow();
  (row.annotation as { regions: Record<string, unknown>[] }).regions = [
    {
      id: "reg_0123456789ab",
      label: "printed_static",
      structure_role: "none",
      legibility: "legible",
      reading_order: 1,
      field_code: null,
      transcription: "HAEMATOLOGY REPORT",
      x: 2,
      y: 3,
      width: 30,
      height: 5,
    },
  ];
  const regions = goldRecord(row).regions as Record<string, unknown>[];
  assert.equal(regions[0].table_data, null);
});

test("the record hash is deterministic and covers table content", () => {
  const first = goldRecord(datasetEligibleRow());
  const second = goldRecord(datasetEligibleRow());
  assert.equal(first.record_sha256, second.record_sha256);
  assert.equal(stableJson(first), stableJson(second));

  const changed = datasetEligibleRow();
  const annotation = changed.annotation as {
    regions: { table_data: { cells: string[][] } }[];
  };
  annotation.regions[0].table_data.cells[1][1] = "9.90";
  assert.notEqual(goldRecord(changed).record_sha256, first.record_sha256);
});
