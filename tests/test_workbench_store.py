from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from dcal_ingestion.cache import label_studio_local_url
from dcal_ingestion.identity import task_ingestion_key
from dcal_ingestion.models import INGESTION_SCHEMA, RENDER_PROFILE
from dcal_workbench.store import UploadItem, VersionConflict, WorkbenchError, WorkbenchStore


ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "config" / "taxonomy" / "bmch-document-taxonomy.v1.json"


def synthetic_png(color: str = "white") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (240, 320), color).save(output, format="PNG")
    return output.getvalue()


def completed_annotation() -> dict[str, object]:
    return {
        "schema_version": "dcal.annotation.v2",
        "document_type": "bmch_admission_form",
        "document_variant": "bmch_admission_form_v1",
        "content_profile": "printed_blank_form",
        "image_quality": ["clear"],
        "notes": "Synthetic test page",
        "regions": [
            {
                "id": "reg_0123456789abcdef",
                "label": "printed_static",
                "structure_role": "form_field",
                "legibility": "legible",
                "reading_order": 1,
                "field_code": "admission_heading",
                "transcription": "SYNTHETIC ADMISSION FORM",
                "x": 10.0,
                "y": 8.0,
                "width": 80.0,
                "height": 10.0,
            }
        ],
    }


def table_annotation() -> dict[str, object]:
    return {
        "schema_version": "dcal.annotation.v2",
        "document_type": "bmch_haematology_report",
        "document_variant": None,
        "content_profile": "printed_filled_form",
        "image_quality": ["clear"],
        "notes": "Synthetic investigation table",
        "regions": [
            {
                "id": "reg_abcdef012345",
                "label": "other_region",
                "structure_role": "table",
                "legibility": "not_applicable",
                "reading_order": 1,
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
                        "printed_static",
                    ],
                    "cells": [
                        ["Test", "Result", "Unit", "Reference"],
                        ["White Blood Cells", "07.50", "10^9/L", "4.00 - 11.00"],
                        ["Haemoglobin", "13.40", "g/dL", "13 - 18"],
                    ],
                },
                "x": 8.0,
                "y": 31.0,
                "width": 84.0,
                "height": 52.0,
            }
        ],
    }


class WorkbenchStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = WorkbenchStore(root / "workbench.sqlite3", root / "images", TAXONOMY)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_manual_upload_is_deduplicated_and_not_export_eligible(self) -> None:
        upload = UploadItem(synthetic_png(), "image/png")
        first = self.store.upload_sources([upload])
        second = self.store.upload_sources([upload])
        self.assertTrue(first[0]["created"])
        self.assertFalse(second[0]["created"])
        task = self.store.get_task(first[0]["id"])
        self.assertFalse(task["dataset_eligible"])
        saved = self.store.save_task(
            task["id"],
            annotation=completed_annotation(),
            expected_version=task["version"],
            actor="Synthetic Annotator",
            status="completed",
        )
        self.assertEqual("completed", saved["status"])
        content, summary = self.store.export_gold()
        self.assertEqual("", content)
        self.assertEqual(1, summary["skipped_manual_without_grouping"])
        reopened = self.store.save_task(
            saved["id"],
            annotation=saved["annotation"],
            expected_version=saved["version"],
            actor="Synthetic Annotator",
        )
        self.assertEqual("in_progress", reopened["status"])
        content, summary = self.store.export_gold()
        self.assertEqual("", content)
        self.assertEqual(0, summary["skipped_manual_without_grouping"])

    def test_drive_import_upgrades_manual_page_and_exports_gold(self) -> None:
        uploaded = self.store.upload_sources([UploadItem(synthetic_png("ivory"), "image/png")])
        task = self.store.get_task(uploaded[0]["id"])
        with self.store._connect() as connection:  # test-only identity inspection
            sha = connection.execute(
                "SELECT source_sha256 FROM tasks WHERE id=1"
            ).fetchone()[0]
        task_id, created = self.store.import_ingestion_task(
            {
                "image": label_studio_local_url(sha),
                "source_object_id": "src_opaque",
                "source_sha256": sha,
                "raw_source_sha256": "a" * 64,
                "patient_group_id": "pat_opaque",
                "encounter_group_id": "enc_opaque",
                "writer_group_ids": [],
                "source_page_index": 1,
                "annotation_schema_version": "dcal.annotation.v1",
                "ingestion_schema_version": INGESTION_SCHEMA,
                "render_profile": RENDER_PROFILE,
                "dcal_ingestion_key": task_ingestion_key(sha),
            }
        )
        self.assertFalse(created)
        self.assertEqual(1, task_id)
        upgraded = self.store.get_task(task["id"])
        self.assertTrue(upgraded["dataset_eligible"])
        completed = self.store.save_task(
            upgraded["id"],
            annotation=completed_annotation(),
            expected_version=upgraded["version"],
            actor="Synthetic Annotator",
            status="completed",
        )
        content, summary = self.store.export_gold()
        record = json.loads(content)
        self.assertEqual(1, summary["exported"])
        self.assertEqual("dcal_workbench", record["annotation"]["source"])
        self.assertEqual("pat_opaque", record["source"]["patient_group_id"])
        self.assertEqual(completed["id"], record["annotation"]["workbench_task_id"])

    def test_structured_table_survives_save_and_gold_export(self) -> None:
        uploaded = self.store.upload_sources([UploadItem(synthetic_png("linen"), "image/png")])
        with self.store._connect() as connection:  # test-only identity inspection
            sha = connection.execute(
                "SELECT source_sha256 FROM tasks WHERE id=1"
            ).fetchone()[0]
        self.store.import_ingestion_task(
            {
                "image": label_studio_local_url(sha),
                "source_object_id": "src_opaque",
                "source_sha256": sha,
                "raw_source_sha256": "a" * 64,
                "patient_group_id": "pat_opaque",
                "encounter_group_id": "enc_opaque",
                "writer_group_ids": [],
                "source_page_index": 1,
                "annotation_schema_version": "dcal.annotation.v1",
                "ingestion_schema_version": INGESTION_SCHEMA,
                "render_profile": RENDER_PROFILE,
                "dcal_ingestion_key": task_ingestion_key(sha),
            }
        )
        task = self.store.get_task(uploaded[0]["id"])
        saved = self.store.save_task(
            task["id"],
            annotation=table_annotation(),
            expected_version=task["version"],
            actor="Synthetic Annotator",
            status="completed",
        )
        stored_table = saved["annotation"]["regions"][0]["table_data"]
        self.assertEqual(3, stored_table["rows"])
        self.assertEqual("07.50", stored_table["cells"][1][1])

        content, summary = self.store.export_gold()
        record = json.loads(content)
        self.assertEqual(1, summary["exported"])
        exported_table = record["regions"][0]["table_data"]
        self.assertEqual(stored_table, exported_table)

    def test_table_payload_is_rejected_on_a_non_table_region(self) -> None:
        task_id = self.store.upload_sources(
            [UploadItem(synthetic_png("azure"), "image/png")]
        )[0]["id"]
        task = self.store.get_task(task_id)
        annotation = completed_annotation()
        annotation["regions"][0]["table_data"] = table_annotation()["regions"][0]["table_data"]
        with self.assertRaisesRegex(WorkbenchError, "not marked as a table"):
            self.store.save_task(
                task["id"],
                annotation=annotation,
                expected_version=task["version"],
                actor="Synthetic Annotator",
                status="completed",
            )

    def test_completion_contract_and_optimistic_locking(self) -> None:
        task_id = self.store.upload_sources([UploadItem(synthetic_png("gray"), "image/png")])[0]["id"]
        task = self.store.get_task(task_id)
        with self.assertRaisesRegex(WorkbenchError, "physical document type"):
            self.store.save_task(
                task_id,
                annotation=task["annotation"],
                expected_version=task["version"],
                actor="Synthetic Annotator",
                status="completed",
            )
        first = self.store.save_task(
            task_id,
            annotation=completed_annotation(),
            expected_version=task["version"],
            actor="Synthetic Annotator",
        )
        with self.assertRaises(VersionConflict):
            self.store.save_task(
                task_id,
                annotation=completed_annotation(),
                expected_version=task["version"],
                actor="Another Annotator",
            )
        self.assertEqual(2, first["version"])

    def test_ingestion_rejects_missing_cached_image(self) -> None:
        sha = "b" * 64
        with self.assertRaisesRegex(WorkbenchError, "not present"):
            self.store.import_ingestion_task(
                {
                    "image": label_studio_local_url(sha),
                    "source_object_id": "src_opaque",
                    "source_sha256": sha,
                    "raw_source_sha256": "c" * 64,
                    "patient_group_id": "pat_opaque",
                    "encounter_group_id": "enc_opaque",
                    "writer_group_ids": [],
                    "source_page_index": 1,
                    "annotation_schema_version": "dcal.annotation.v1",
                    "ingestion_schema_version": INGESTION_SCHEMA,
                    "render_profile": RENDER_PROFILE,
                    "dcal_ingestion_key": task_ingestion_key(sha),
                }
            )


if __name__ == "__main__":
    unittest.main()
