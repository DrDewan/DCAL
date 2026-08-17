import assert from "node:assert/strict";
import test from "node:test";

import { blankAnnotation } from "@/lib/contracts";
import { HttpError } from "@/lib/http";
import { validateAnnotation } from "@/lib/validation";

function validRegion() {
  return {
    id: "reg_0123456789ab",
    label: "printed_static",
    structure_role: "none",
    legibility: "legible",
    reading_order: 1,
    field_code: null,
    transcription: "Admission form",
    x: 2,
    y: 3,
    width: 30,
    height: 5,
  };
}

function validTableRegion() {
  return {
    id: "reg_abcdef012345",
    label: "other_region",
    structure_role: "table",
    legibility: "not_applicable",
    reading_order: 1,
    field_code: "cbc_results",
    transcription: "",
    table_data: {
      rows: 3,
      columns: 4,
      header_rows: 1,
      column_labels: ["printed_static", "printed_variable", "printed_static", "printed_static"],
      cells: [
        ["Test", "Result", "Unit", "Reference"],
        ["White Blood Cells", "07.50", "10^9/L", "4.00 - 11.00"],
        ["Haemoglobin", "13.40", "g/dL", "13 - 18"],
      ],
    },
    x: 10,
    y: 20,
    width: 70,
    height: 45,
  };
}

test("a complete clinical annotation is normalized", () => {
  const annotation = {
    ...blankAnnotation(),
    document_type: "bmch_admission_form",
    document_variant: "bmch_admission_form_v1",
    content_profile: "printed_blank_form",
    image_quality: ["clear"],
    regions: [validRegion()],
  };
  const result = validateAnnotation(annotation, true);
  assert.equal(result.schema_version, "dcal.annotation.v2");
  assert.equal(result.regions[0].transcription, "Admission form");
});

test("a clinical or financial page cannot complete without regions", () => {
  for (const documentType of ["bmch_admission_form", "financial_billing_document"]) {
    assert.throws(
      () => validateAnnotation({
        ...blankAnnotation(),
        document_type: documentType,
        content_profile: "printed_document",
      }, true),
      (error) => error instanceof HttpError && error.code === "invalid_annotation",
    );
  }
});

test("an explicitly unknown document may complete without regions", () => {
  const result = validateAnnotation({
    ...blankAnnotation(),
    document_type: "unknown_document",
    content_profile: "unknown",
  }, true);
  assert.equal(result.regions.length, 0);
});

test("readable printed text requires exact transcription at completion", () => {
  const region = { ...validRegion(), transcription: "" };
  assert.throws(() => validateAnnotation({
    ...blankAnnotation(),
    document_type: "bmch_admission_form",
    content_profile: "printed_document",
    regions: [region],
  }, true), HttpError);
});

test("structured table data is preserved", () => {
  const result = validateAnnotation({
    ...blankAnnotation(),
    document_type: "bmch_haematology_report",
    content_profile: "printed_filled_form",
    regions: [validTableRegion()],
  }, true);
  assert.equal(result.regions[0].structure_role, "table");
  assert.equal(result.regions[0].table_data?.rows, 3);
  assert.equal(result.regions[0].table_data?.cells[1][1], "07.50");
});

test("table dimensions and cell matrix must agree", () => {
  const region = validTableRegion();
  region.table_data.cells = [["Test", "Result"]];
  assert.throws(() => validateAnnotation({
    ...blankAnnotation(),
    document_type: "bmch_haematology_report",
    content_profile: "printed_filled_form",
    regions: [region],
  }, false), HttpError);
});
