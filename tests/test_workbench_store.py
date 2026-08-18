from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image

from dcal_ingestion.cache import label_studio_local_url
from dcal_ingestion.identity import task_ingestion_key
from dcal_ingestion.models import INGESTION_SCHEMA, RENDER_PROFILE
from dcal_workbench.store import UploadItem, WorkbenchError, WorkbenchStore


def synthetic_png(color: str = "white") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (240, 320), color).save(output, format="PNG")
    return output.getvalue()


def synthetic_pdf(pages: int = 2) -> bytes:
    document = pymupdf.open()
    for index in range(pages):
        # Distinct geometry per page; identical blank pages would render to
        # identical bytes and correctly deduplicate to a single task.
        document.new_page(width=300 + index * 10, height=400)
    content = document.tobytes()
    document.close()
    return content


def ingestion_payload(sha256: str) -> dict[str, object]:
    return {
        "image": label_studio_local_url(sha256),
        "source_object_id": "src_opaque",
        "source_sha256": sha256,
        "raw_source_sha256": "a" * 64,
        "patient_group_id": "pat_opaque",
        "encounter_group_id": "enc_opaque",
        "writer_group_ids": [],
        "source_page_index": 1,
        "annotation_schema_version": "dcal.annotation.v1",
        "ingestion_schema_version": INGESTION_SCHEMA,
        "render_profile": RENDER_PROFILE,
        "dcal_ingestion_key": task_ingestion_key(sha256),
    }


class WorkbenchStoreTests(unittest.TestCase):
    """The local store is an ingestion sink and upload renderer only.

    Annotation, validation, and gold export belong to the hosted workbench.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = WorkbenchStore(root / "workbench.sqlite3", root / "images")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def page_checksum(self, task_id: str) -> str:
        numeric = int(task_id.split("_", 1)[1])
        with self.store._connect() as connection:  # test-only identity inspection
            return connection.execute(
                "SELECT source_sha256 FROM tasks WHERE id=?", (numeric,)
            ).fetchone()[0]

    def test_manual_upload_is_deduplicated_and_not_dataset_eligible(self) -> None:
        upload = UploadItem(synthetic_png(), "image/png")
        first = self.store.upload_sources([upload])
        second = self.store.upload_sources([upload])
        self.assertTrue(first[0]["created"])
        self.assertFalse(second[0]["created"])
        task = self.store.get_task(first[0]["id"])
        self.assertFalse(task["dataset_eligible"])
        self.assertEqual("manual_upload", task["source_origin"])

    def test_a_multi_page_pdf_becomes_one_task_per_page(self) -> None:
        results = self.store.upload_sources([UploadItem(synthetic_pdf(3), "application/pdf")])
        self.assertEqual(3, len(results))
        self.assertEqual(3, len({item["id"] for item in results}))
        for item in results:
            self.assertTrue(item["created"])
            self.assertTrue(self.store.image_path(item["id"]).is_file())

    def test_drive_import_upgrades_a_manual_page_to_dataset_eligible(self) -> None:
        uploaded = self.store.upload_sources([UploadItem(synthetic_png("ivory"), "image/png")])
        sha = self.page_checksum(uploaded[0]["id"])
        task_id, created = self.store.import_ingestion_task(ingestion_payload(sha))
        self.assertFalse(created)
        upgraded = self.store.get_task(uploaded[0]["id"])
        self.assertEqual(task_id, int(uploaded[0]["id"].split("_", 1)[1]))
        self.assertTrue(upgraded["dataset_eligible"])
        self.assertEqual("google_drive", upgraded["source_origin"])

    def test_ingestion_index_exposes_every_task_key(self) -> None:
        uploaded = self.store.upload_sources([UploadItem(synthetic_png("linen"), "image/png")])
        sha = self.page_checksum(uploaded[0]["id"])
        index = self.store.task_index()
        self.assertIn(task_ingestion_key(sha), index)

    def test_ingestion_rejects_a_key_that_does_not_match_the_checksum(self) -> None:
        uploaded = self.store.upload_sources([UploadItem(synthetic_png("beige"), "image/png")])
        sha = self.page_checksum(uploaded[0]["id"])
        payload = ingestion_payload(sha)
        payload["dcal_ingestion_key"] = task_ingestion_key("f" * 64)
        with self.assertRaisesRegex(WorkbenchError, "does not match page checksum"):
            self.store.import_ingestion_task(payload)

    def test_ingestion_rejects_missing_cached_image(self) -> None:
        with self.assertRaisesRegex(WorkbenchError, "not present"):
            self.store.import_ingestion_task(ingestion_payload("b" * 64))


if __name__ == "__main__":
    unittest.main()
