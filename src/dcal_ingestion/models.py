from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DRIVE_LAYOUT_SCHEMA = "dcal.drive-layout.v1"
INGESTION_SCHEMA = "dcal.ingestion.v1"
RENDER_PROFILE = "dcal.render.300dpi-rgb-png.v1"


@dataclass(frozen=True)
class DriveLayout:
    root: str
    inbox: str
    source_archive: str
    page_store: str
    quarantine: str
    dataset_exports: str
    manifests: str

    def as_dict(self) -> dict[str, str]:
        return {
            "schema_version": DRIVE_LAYOUT_SCHEMA,
            "root": self.root,
            "inbox": self.inbox,
            "source_archive": self.source_archive,
            "page_store": self.page_store,
            "quarantine": self.quarantine,
            "dataset_exports": self.dataset_exports,
            "manifests": self.manifests,
        }


@dataclass(frozen=True)
class IngestionCandidate:
    file_id: str
    parent_id: str
    patient_folder_id: str
    encounter_folder_id: str
    mime_type: str
    name: str
    size: int | None = None
    app_properties: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderedPage:
    page_index: int
    content: bytes
    sha256: str
    width: int
    height: int
    mime_type: str = "image/png"
    render_profile: str = RENDER_PROFILE


@dataclass(frozen=True)
class StoredDriveFile:
    file_id: str
    mime_type: str
    size: int | None
    app_properties: dict[str, str]
    content_restrictions: tuple[dict[str, Any], ...] = ()

    @property
    def expected_sha256(self) -> str | None:
        return self.app_properties.get("dcal_sha256")

    @property
    def is_read_only(self) -> bool:
        return any(item.get("readOnly") is True for item in self.content_restrictions)


@dataclass
class SyncSummary:
    sources_seen: int = 0
    sources_completed: int = 0
    sources_quarantined: int = 0
    sources_failed: int = 0
    layout_errors: int = 0
    pages_rendered: int = 0
    pages_new: int = 0
    pages_duplicate: int = 0
    tasks_created: int = 0
    tasks_reused: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            name: int(value)
            for name, value in vars(self).items()
        }

    @property
    def successful(self) -> bool:
        return self.sources_failed == 0 and self.layout_errors == 0


class SourceRejected(ValueError):
    """A permanent, safely reportable source validation failure."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class DriveContractError(RuntimeError):
    """The Drive layout or API response violates the DCAL contract."""


class LabelStudioError(RuntimeError):
    """A safe Label Studio integration failure with no task data in the message."""


class AnnotationGatewayError(RuntimeError):
    """A safe first-party annotation-workbench integration failure."""
