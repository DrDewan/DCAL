from __future__ import annotations

import copy
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from dcal_ingestion.ledger import IngestionLedger
from dcal_ingestion.models import (
    DriveLayout,
    IngestionCandidate,
    RenderedPage,
    StoredDriveFile,
)
from dcal_ingestion.service import IngestionService, IngestionSettings


TEST_KEY = b"0123456789abcdef0123456789abcdef"
LAYOUT = DriveLayout(
    root="root",
    inbox="inbox",
    source_archive="archive",
    page_store="pages",
    quarantine="quarantine",
    dataset_exports="exports",
    manifests="manifests",
)


def synthetic_png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (160, 100), "white").save(output, format="PNG")
    return output.getvalue()


class FakeDrive:
    def __init__(self, candidates: list[IngestionCandidate], content: dict[str, bytes]):
        self.candidates = candidates
        self.content = content
        self.layout_errors = 0
        self.pages: dict[str, tuple[bytes, StoredDriveFile]] = {}
        self.archived: list[str] = []
        self.quarantined: list[tuple[str, str]] = []

    def bootstrap_layout(self, root_folder_id: str) -> DriveLayout:
        return LAYOUT

    def resolve_layout(self, root_folder_id: str) -> DriveLayout:
        return LAYOUT

    def scan_inbox(self, layout: DriveLayout):
        return list(self.candidates), self.layout_errors

    def download(self, file_id: str, *, max_bytes: int) -> bytes:
        content = self.content[file_id]
        if len(content) > max_bytes:
            raise ValueError("too large")
        return content

    def ensure_page(
        self,
        layout: DriveLayout,
        page: RenderedPage,
        app_properties: dict[str, str],
    ):
        existing = self.pages.get(page.sha256)
        if existing:
            return existing[1], False
        stored = StoredDriveFile(
            file_id=f"stored-{len(self.pages) + 1}",
            mime_type="image/png",
            size=len(page.content),
            app_properties=copy.deepcopy(app_properties),
            content_restrictions=({"readOnly": True},),
        )
        self.pages[page.sha256] = (page.content, stored)
        self.content[stored.file_id] = page.content
        return stored, True

    def archive_source(self, layout: DriveLayout, candidate: IngestionCandidate, **kwargs):
        self.archived.append(candidate.file_id)

    def quarantine_source(
        self,
        layout: DriveLayout,
        candidate: IngestionCandidate,
        *,
        error_code: str,
    ):
        self.quarantined.append((candidate.file_id, error_code))

    def list_stored_files(self, folder_id: str):
        return [value[1] for value in self.pages.values()]


class FakeLabelStudio:
    def __init__(self):
        self.index: dict[str, int] = {}
        self.tasks: dict[int, dict[str, object]] = {}
        self.fail_create = False

    def task_index(self) -> dict[str, int]:
        return dict(self.index)

    def create_task(self, data: dict[str, object]) -> int:
        if self.fail_create:
            raise RuntimeError("synthetic infrastructure failure")
        task_id = len(self.tasks) + 100
        self.tasks[task_id] = copy.deepcopy(data)
        self.index[str(data["dcal_ingestion_key"])] = task_id
        return task_id


class IngestionServiceTests(unittest.TestCase):
    def candidate(self, file_id: str = "drive-file-id") -> IngestionCandidate:
        return IngestionCandidate(
            file_id=file_id,
            parent_id="encounter-folder-id",
            patient_folder_id="patient-folder-id",
            encounter_folder_id="encounter-folder-id",
            mime_type="image/png",
            name="REAL PATIENT NAME.png",
            size=len(synthetic_png()),
        )

    def service(self, directory: str, drive: FakeDrive, label_studio: FakeLabelStudio):
        ledger = IngestionLedger(Path(directory) / "ledger.sqlite3")
        service = IngestionService(
            drive=drive,
            label_studio=label_studio,
            ledger=ledger,
            layout=LAYOUT,
            settings=IngestionSettings(
                hmac_key=TEST_KEY, cache_root=Path(directory) / "cache"
            ),
        )
        return service, ledger

    def test_valid_source_is_archived_and_creates_one_private_task(self) -> None:
        candidate = self.candidate()
        drive = FakeDrive([candidate], {candidate.file_id: synthetic_png()})
        label_studio = FakeLabelStudio()
        with tempfile.TemporaryDirectory() as directory:
            service, ledger = self.service(directory, drive, label_studio)
            try:
                summary = service.sync_once()
                lineage_count = ledger.connection.execute(
                    "SELECT COUNT(*) FROM source_pages"
                ).fetchone()[0]
            finally:
                ledger.close()
            self.assertTrue(summary.successful)
            self.assertEqual(1, summary.sources_completed)
            self.assertEqual(1, summary.pages_new)
            self.assertEqual(1, summary.tasks_created)
            self.assertEqual(1, lineage_count)
            self.assertEqual([candidate.file_id], drive.archived)
            task = next(iter(label_studio.tasks.values()))
            serialized = repr(task)
            for raw_value in (
                candidate.file_id,
                candidate.patient_folder_id,
                candidate.encounter_folder_id,
                candidate.name,
            ):
                self.assertNotIn(raw_value, serialized)
            self.assertEqual([], task["writer_group_ids"])
            self.assertTrue(str(task["image"]).startswith("/data/local-files/?d=pages/"))

    def test_retry_reuses_drive_page_and_label_studio_task(self) -> None:
        candidate = self.candidate()
        drive = FakeDrive([candidate], {candidate.file_id: synthetic_png()})
        label_studio = FakeLabelStudio()
        with tempfile.TemporaryDirectory() as directory:
            service, ledger = self.service(directory, drive, label_studio)
            try:
                first = service.sync_once()
                second = service.sync_once()
            finally:
                ledger.close()
            self.assertEqual(1, first.tasks_created)
            self.assertEqual(0, second.tasks_created)
            self.assertEqual(1, second.tasks_reused)
            self.assertEqual(1, second.pages_duplicate)
            self.assertEqual(1, len(label_studio.tasks))

    def test_duplicate_page_across_sources_creates_one_task(self) -> None:
        first = self.candidate("drive-file-1")
        second = IngestionCandidate(
            **{
                **vars(self.candidate("drive-file-2")),
                "patient_folder_id": "another-patient-folder",
            }
        )
        content = synthetic_png()
        drive = FakeDrive([first, second], {first.file_id: content, second.file_id: content})
        label_studio = FakeLabelStudio()
        with tempfile.TemporaryDirectory() as directory:
            service, ledger = self.service(directory, drive, label_studio)
            try:
                summary = service.sync_once()
                lineage_count = ledger.connection.execute(
                    "SELECT COUNT(*) FROM source_pages"
                ).fetchone()[0]
            finally:
                ledger.close()
            self.assertEqual(2, summary.sources_completed)
            self.assertEqual(1, summary.tasks_created)
            self.assertEqual(1, summary.tasks_reused)
            self.assertEqual(1, len(label_studio.tasks))
            self.assertEqual(2, lineage_count)

    def test_unsupported_source_is_quarantined_without_download(self) -> None:
        candidate = IngestionCandidate(
            **{**vars(self.candidate()), "mime_type": "application/msword"}
        )
        drive = FakeDrive([candidate], {})
        label_studio = FakeLabelStudio()
        with tempfile.TemporaryDirectory() as directory:
            service, ledger = self.service(directory, drive, label_studio)
            try:
                summary = service.sync_once()
            finally:
                ledger.close()
            self.assertEqual(1, summary.sources_quarantined)
            self.assertEqual(
                [(candidate.file_id, "unsupported_media_type")], drive.quarantined
            )

    def test_infrastructure_failure_leaves_source_out_of_quarantine(self) -> None:
        candidate = self.candidate()
        drive = FakeDrive([candidate], {candidate.file_id: synthetic_png()})
        label_studio = FakeLabelStudio()
        label_studio.fail_create = True
        with tempfile.TemporaryDirectory() as directory:
            service, ledger = self.service(directory, drive, label_studio)
            try:
                summary = service.sync_once()
            finally:
                ledger.close()
            self.assertEqual(1, summary.sources_failed)
            self.assertFalse(summary.successful)
            self.assertEqual([], drive.quarantined)
            self.assertEqual([], drive.archived)

    def test_layout_errors_make_sync_unsuccessful(self) -> None:
        drive = FakeDrive([], {})
        drive.layout_errors = 2
        with tempfile.TemporaryDirectory() as directory:
            service, ledger = self.service(directory, drive, FakeLabelStudio())
            try:
                summary = service.sync_once()
            finally:
                ledger.close()
        self.assertEqual(2, summary.layout_errors)
        self.assertFalse(summary.successful)


if __name__ == "__main__":
    unittest.main()
