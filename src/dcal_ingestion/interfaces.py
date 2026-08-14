from __future__ import annotations

from typing import Protocol

from .models import DriveLayout, IngestionCandidate, RenderedPage, StoredDriveFile


class DriveGateway(Protocol):
    def bootstrap_layout(self, root_folder_id: str) -> DriveLayout: ...

    def resolve_layout(self, root_folder_id: str) -> DriveLayout: ...

    def scan_inbox(
        self, layout: DriveLayout
    ) -> tuple[list[IngestionCandidate], int]: ...

    def download(self, file_id: str, *, max_bytes: int) -> bytes: ...

    def ensure_page(
        self,
        layout: DriveLayout,
        page: RenderedPage,
        app_properties: dict[str, str],
    ) -> tuple[StoredDriveFile, bool]: ...

    def archive_source(
        self,
        layout: DriveLayout,
        candidate: IngestionCandidate,
        *,
        raw_sha256: str,
        page_count: int,
        patient_group_id: str,
        encounter_group_id: str,
    ) -> None: ...

    def quarantine_source(
        self,
        layout: DriveLayout,
        candidate: IngestionCandidate,
        *,
        error_code: str,
    ) -> None: ...

    def list_stored_files(self, folder_id: str) -> list[StoredDriveFile]: ...


class AnnotationGateway(Protocol):
    def task_index(self) -> dict[str, int]: ...

    def create_task(self, data: dict[str, object]) -> int: ...


# Compatibility name for the optional legacy adapter.
LabelStudioGateway = AnnotationGateway
