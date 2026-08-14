from __future__ import annotations

import hashlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image

from dcal_ingestion.cache import label_studio_local_url, write_cache_content
from dcal_ingestion.identity import opaque_id, task_ingestion_key, validate_hmac_key
from dcal_ingestion.ledger import IngestionLedger, PageRecord
from dcal_ingestion.models import SourceRejected
from dcal_ingestion.render import render_source


TEST_KEY = b"0123456789abcdef0123456789abcdef"


class IdentityTests(unittest.TestCase):
    def test_opaque_ids_are_stable_and_namespace_separated(self) -> None:
        first = opaque_id(TEST_KEY, "patient", "folder-1", prefix="pat")
        second = opaque_id(TEST_KEY, "patient", "folder-1", prefix="pat")
        encounter = opaque_id(TEST_KEY, "encounter", "folder-1", prefix="enc")
        self.assertEqual(first, second)
        self.assertNotEqual(first.split("_", 1)[1], encounter.split("_", 1)[1])
        self.assertNotIn("folder-1", first)

    def test_weak_hmac_keys_are_rejected(self) -> None:
        for key in (b"short", b"x" * 32, b"replace-with-a-real-key" * 2):
            with self.subTest(key=key[:8]):
                with self.assertRaises(ValueError):
                    validate_hmac_key(key)

    def test_task_key_is_content_addressed(self) -> None:
        key = task_ingestion_key("a" * 64)
        self.assertRegex(key, r"^task_[0-9a-f]{32}$")


class RenderingTests(unittest.TestCase):
    @staticmethod
    def jpeg_bytes() -> bytes:
        output = io.BytesIO()
        Image.new("RGB", (120, 80), "white").save(output, format="JPEG", quality=95)
        return output.getvalue()

    def test_image_render_is_deterministic_png(self) -> None:
        source = self.jpeg_bytes()
        first = render_source(source, "image/jpeg")
        second = render_source(source, "image/jpeg")
        self.assertEqual(1, len(first))
        self.assertEqual(first[0].content, second[0].content)
        self.assertEqual(hashlib.sha256(first[0].content).hexdigest(), first[0].sha256)
        self.assertTrue(first[0].content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual((120, 80), (first[0].width, first[0].height))

    def test_pdf_is_rendered_at_production_resolution(self) -> None:
        document = pymupdf.open()
        page = document.new_page(width=200, height=300)
        page.insert_text((20, 40), "Synthetic DCAL test")
        content = document.tobytes()
        document.close()
        pages = render_source(content, "application/pdf")
        self.assertEqual(1, len(pages))
        self.assertGreaterEqual(pages[0].width, 830)
        self.assertGreaterEqual(pages[0].height, 1240)

    def test_unsupported_and_empty_sources_are_rejected(self) -> None:
        with self.assertRaisesRegex(SourceRejected, "empty"):
            render_source(b"", "image/png")
        with self.assertRaisesRegex(SourceRejected, "only PDF"):
            render_source(b"not a document", "text/plain")


class CacheAndLedgerTests(unittest.TestCase):
    def test_cache_is_content_verified_and_uses_label_studio_path(self) -> None:
        content = b"synthetic page bytes"
        sha = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = write_cache_content(directory, sha, content)
            self.assertEqual(content, path.read_bytes())
            self.assertEqual(
                f"/data/local-files/?d=pages/{sha[:2]}/{sha}.png",
                label_studio_local_url(sha),
            )
            with self.assertRaisesRegex(ValueError, "mismatched"):
                write_cache_content(directory, sha, b"different")

    def test_ledger_persists_only_normalized_page_identity(self) -> None:
        sha = "b" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            with IngestionLedger(path) as ledger:
                ledger.record_page(
                    PageRecord(
                        page_sha256=sha,
                        source_key="raw_opaque",
                        source_object_id="src_opaque",
                        patient_group_id="pat_opaque",
                        encounter_group_id="enc_opaque",
                        page_index=1,
                        local_path=f"pages/bb/{sha}.png",
                        label_studio_task_id=91,
                    )
                )
                ledger.record_page(
                    PageRecord(
                        page_sha256=sha,
                        source_key="raw_opaque",
                        source_object_id="src_opaque_second_occurrence",
                        patient_group_id="pat_opaque",
                        encounter_group_id="enc_opaque",
                        page_index=2,
                        local_path=f"pages/bb/{sha}.png",
                        label_studio_task_id=91,
                    )
                )
                ledger.record_source(
                    source_key="raw_opaque",
                    raw_sha256="c" * 64,
                    patient_group_id="pat_opaque",
                    encounter_group_id="enc_opaque",
                    status="complete",
                    page_count=1,
                )
            with IngestionLedger(path) as ledger:
                record = ledger.page(sha)
                self.assertIsNotNone(record)
                self.assertEqual(91, record.label_studio_task_id)  # type: ignore[union-attr]
                occurrences = ledger.connection.execute(
                    "SELECT COUNT(*) FROM source_pages WHERE page_sha256=?", (sha,)
                ).fetchone()[0]
                self.assertEqual(2, occurrences)
            connection = sqlite3.connect(path)
            dump = "\n".join(connection.iterdump())
            connection.close()
            self.assertNotIn("drive-file-id", dump)

    def test_version_one_ledger_migrates_page_lineage(self) -> None:
        sha = "d" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            connection = sqlite3.connect(path)
            connection.executescript(
                """
                CREATE TABLE ledger_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT INTO ledger_meta(key, value)
                VALUES('schema_version', '1');

                CREATE TABLE sources (
                    source_key TEXT PRIMARY KEY,
                    raw_sha256 TEXT,
                    patient_group_id TEXT NOT NULL,
                    encounter_group_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    page_count INTEGER,
                    error_code TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE pages (
                    page_sha256 TEXT PRIMARY KEY,
                    source_object_id TEXT NOT NULL,
                    patient_group_id TEXT NOT NULL,
                    encounter_group_id TEXT NOT NULL,
                    page_index INTEGER NOT NULL,
                    local_path TEXT NOT NULL,
                    label_studio_task_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            connection.execute(
                """
                INSERT INTO pages(
                    page_sha256, source_object_id, patient_group_id,
                    encounter_group_id, page_index, local_path,
                    label_studio_task_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sha,
                    "src_legacy",
                    "pat_legacy",
                    "enc_legacy",
                    3,
                    f"pages/dd/{sha}.png",
                    44,
                ),
            )
            connection.commit()
            connection.close()

            with IngestionLedger(path) as ledger:
                version = ledger.connection.execute(
                    "SELECT value FROM ledger_meta WHERE key='schema_version'"
                ).fetchone()[0]
                record = ledger.page(sha)

            self.assertEqual("2", version)
            self.assertIsNotNone(record)
            self.assertEqual("src_legacy", record.source_object_id)  # type: ignore[union-attr]
            self.assertTrue(record.source_key.startswith("legacy_"))  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
