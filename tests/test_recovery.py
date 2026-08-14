from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from dcal_ingestion.models import DriveLayout, StoredDriveFile
from dcal_ingestion.recovery import audit_drive, restore_page_cache


LAYOUT = DriveLayout(
    root="root",
    inbox="inbox",
    source_archive="archive",
    page_store="pages",
    quarantine="quarantine",
    dataset_exports="exports",
    manifests="manifests",
)


class RecoveryDrive:
    def __init__(self, page_content: bytes):
        self.page_content = page_content
        self.sha = hashlib.sha256(page_content).hexdigest()
        self.files = {
            "pages": [
                StoredDriveFile(
                    file_id="page-1",
                    mime_type="image/png",
                    size=len(page_content),
                    app_properties={"dcal_sha256": self.sha},
                    content_restrictions=({"readOnly": True},),
                )
            ],
            "archive": [
                StoredDriveFile(
                    file_id="raw-1",
                    mime_type="image/png",
                    size=len(page_content),
                    app_properties={"dcal_sha256": self.sha},
                    content_restrictions=({"readOnly": True},),
                )
            ],
        }

    def list_stored_files(self, folder_id: str):
        return list(self.files.get(folder_id, []))

    def download(self, file_id: str, *, max_bytes: int):
        return self.page_content


class RecoveryTests(unittest.TestCase):
    def test_audit_checks_archive_and_page_store(self) -> None:
        drive = RecoveryDrive(b"synthetic recovery bytes")
        summary = audit_drive(drive, LAYOUT)
        self.assertTrue(summary.successful)
        self.assertEqual(2, summary.checked)
        self.assertEqual(2, summary.valid)

    def test_audit_detects_unlocked_and_corrupt_objects(self) -> None:
        drive = RecoveryDrive(b"original")
        stored = drive.files["pages"][0]
        drive.files["pages"][0] = StoredDriveFile(
            file_id=stored.file_id,
            mime_type=stored.mime_type,
            size=stored.size,
            app_properties={"dcal_sha256": "f" * 64},
            content_restrictions=(),
        )
        summary = audit_drive(drive, LAYOUT)
        self.assertFalse(summary.successful)
        self.assertEqual(1, summary.unlocked)
        self.assertEqual(1, summary.checksum_mismatch)

    def test_cache_restore_is_idempotent(self) -> None:
        drive = RecoveryDrive(b"synthetic recovery bytes")
        with tempfile.TemporaryDirectory() as directory:
            first = restore_page_cache(drive, LAYOUT, directory)
            second = restore_page_cache(drive, LAYOUT, directory)
            self.assertEqual(1, first.restored)
            self.assertEqual(1, second.already_present)
            path = Path(directory) / "pages" / drive.sha[:2] / f"{drive.sha}.png"
            self.assertEqual(drive.page_content, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
