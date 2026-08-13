from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from dcal_annotations import ExportValidationError, load_taxonomy, normalize_export


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPOSITORY_ROOT / "examples" / "label-studio-export.valid.json"


class ExportValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.taxonomy = load_taxonomy()

    def payload(self) -> list[dict]:
        return copy.deepcopy(self.fixture)

    def results(self, payload: list[dict]) -> list[dict]:
        return payload[0]["annotations"][0]["result"]

    def result(self, payload: list[dict], from_name: str, region_id: str | None = None) -> dict:
        for item in self.results(payload):
            if item.get("from_name") == from_name and (
                region_id is None or item.get("id") == region_id
            ):
                return item
        self.fail(f"missing fixture result {from_name}/{region_id}")

    def assert_invalid(self, payload: object, expected: str) -> None:
        with self.assertRaisesRegex(ExportValidationError, expected):
            normalize_export(payload, self.taxonomy)

    def test_valid_export_normalizes_without_image_uri(self) -> None:
        records = normalize_export(self.payload(), self.taxonomy)
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual("dcal.gold.v1", record["schema_version"])
        self.assertNotIn("image", record["source"])
        self.assertEqual(
            ["printed_variable", "handwriting"],
            [region["label"] for region in record["regions"]],
        )
        self.assertEqual(64, len(record["record_sha256"]))

    def test_normalization_is_deterministic(self) -> None:
        first = normalize_export(self.payload(), self.taxonomy)
        second = normalize_export(self.payload(), self.taxonomy)
        self.assertEqual(first, second)

    def test_unknown_physical_type_is_rejected(self) -> None:
        payload = self.payload()
        self.result(payload, "physical_document_type")["value"]["choices"] = ["invented"]
        self.assert_invalid(payload, "unknown physical document type")

    def test_variant_must_belong_to_physical_type(self) -> None:
        payload = self.payload()
        self.result(payload, "physical_document_variant")["value"]["choices"] = [
            "bmch_treatment_continuation_v1"
        ]
        self.assert_invalid(payload, "does not belong")

    def test_clear_cannot_be_combined_with_a_defect(self) -> None:
        payload = self.payload()
        self.result(payload, "image_quality")["value"]["choices"] = ["clear", "blur"]
        self.assert_invalid(payload, "cannot be combined")

    def test_readable_text_requires_a_transcription(self) -> None:
        payload = self.payload()
        self.results(payload).remove(
            self.result(payload, "transcription", "region-handwriting-1")
        )
        self.assert_invalid(payload, "requires exact transcription")

    def test_illegible_text_rejects_an_invented_transcription(self) -> None:
        payload = self.payload()
        self.result(payload, "legibility", "region-handwriting-1")["value"]["choices"] = [
            "illegible"
        ]
        self.assert_invalid(payload, "must not contain transcription")

    def test_duplicate_reading_order_is_rejected(self) -> None:
        payload = self.payload()
        self.result(payload, "reading_order", "region-handwriting-1")["value"]["number"] = 1
        self.assert_invalid(payload, "reading_order values must be unique")

    def test_out_of_bounds_geometry_is_rejected(self) -> None:
        payload = self.payload()
        self.result(payload, "region_label", "region-handwriting-1")["value"]["width"] = 95
        self.assert_invalid(payload, "right page boundary")

    def test_multiple_annotations_require_one_ground_truth(self) -> None:
        payload = self.payload()
        second = copy.deepcopy(payload[0]["annotations"][0])
        second["id"] = 1002
        payload[0]["annotations"].append(second)
        self.assert_invalid(payload, "exactly one active annotation")

        payload[0]["annotations"][1]["ground_truth"] = True
        records = normalize_export(payload, self.taxonomy)
        self.assertEqual(1002, records[0]["annotation"]["label_studio_annotation_id"])

    def test_clinical_page_requires_a_region(self) -> None:
        payload = self.payload()
        payload[0]["annotations"][0]["result"] = [
            item
            for item in self.results(payload)
            if item.get("from_name")
            not in {
                "region_label",
                "reading_order",
                "legibility",
                "structure_role",
                "semantic_region_type",
                "transcription",
                "field_code",
            }
        ]
        self.assert_invalid(payload, "clinical physical pages require")

    def test_non_catalog_page_may_have_no_regions(self) -> None:
        payload = self.payload()
        self.result(payload, "physical_document_type")["value"]["choices"] = [
            "blank_or_noninformative_page"
        ]
        self.results(payload).remove(self.result(payload, "physical_document_variant"))
        payload[0]["annotations"][0]["result"] = [
            item
            for item in self.results(payload)
            if item.get("from_name")
            not in {
                "region_label",
                "reading_order",
                "legibility",
                "structure_role",
                "semantic_region_type",
                "transcription",
                "field_code",
            }
        ]
        records = normalize_export(payload, self.taxonomy)
        self.assertEqual([], records[0]["regions"])

    def test_orphaned_region_control_is_rejected(self) -> None:
        payload = self.payload()
        self.result(payload, "legibility", "region-handwriting-1")["id"] = "missing-region"
        self.assert_invalid(payload, "reference missing geometry IDs")

    def test_duplicate_source_hash_is_rejected(self) -> None:
        payload = self.payload()
        duplicate = copy.deepcopy(payload[0])
        duplicate["id"] = 102
        duplicate["data"]["source_object_id"] = "synthetic-source-002"
        payload.append(duplicate)
        self.assert_invalid(payload, "duplicate source SHA-256")


if __name__ == "__main__":
    unittest.main()
