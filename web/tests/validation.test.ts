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
