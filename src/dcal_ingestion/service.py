from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .cache import label_studio_local_url, page_relative_path, write_page_cache
from .identity import opaque_id, task_ingestion_key, validate_hmac_key
from .interfaces import AnnotationGateway, DriveGateway
from .ledger import IngestionLedger, PageRecord
from .models import (
    INGESTION_SCHEMA,
    DriveLayout,
    IngestionCandidate,
    SourceRejected,
    SyncSummary,
)
from .render import MAX_SOURCE_BYTES, SUPPORTED_IMAGE_MIME_TYPES, render_source


SUPPORTED_SOURCE_MIME_TYPES = SUPPORTED_IMAGE_MIME_TYPES | {"application/pdf"}


@dataclass(frozen=True)
class IngestionSettings:
    hmac_key: bytes
    cache_root: Path

    def __post_init__(self) -> None:
        validate_hmac_key(self.hmac_key)


class IngestionService:
    def __init__(
        self,
        *,
        drive: DriveGateway,
        annotation_gateway: AnnotationGateway,
        ledger: IngestionLedger,
        layout: DriveLayout,
        settings: IngestionSettings,
    ):
        self.drive = drive
        self.annotation_gateway = annotation_gateway
        self.ledger = ledger
        self.layout = layout
        self.settings = settings

    def _identities(self, candidate: IngestionCandidate) -> tuple[str, str, str]:
        patient_group_id = opaque_id(
            self.settings.hmac_key,
            "drive-patient-folder",
            candidate.patient_folder_id,
            prefix="pat",
        )
        encounter_group_id = opaque_id(
            self.settings.hmac_key,
            "drive-encounter-folder",
            candidate.encounter_folder_id,
            prefix="enc",
        )
        source_key = opaque_id(
            self.settings.hmac_key,
            "drive-source-file",
            candidate.file_id,
            prefix="raw",
        )
        return patient_group_id, encounter_group_id, source_key

    def _process_source(
        self,
        candidate: IngestionCandidate,
        task_index: dict[str, int],
        summary: SyncSummary,
    ) -> None:
        patient_group_id, encounter_group_id, source_key = self._identities(candidate)
        if candidate.mime_type not in SUPPORTED_SOURCE_MIME_TYPES:
            raise SourceRejected(
                "unsupported_media_type",
                "source is not a supported PDF or image",
            )
        if candidate.size is not None and candidate.size > MAX_SOURCE_BYTES:
            raise SourceRejected(
                "source_too_large",
                f"source exceeds the {MAX_SOURCE_BYTES // (1024 * 1024)} MiB safety limit",
            )

        raw_content = self.drive.download(
            candidate.file_id, max_bytes=MAX_SOURCE_BYTES
        )
        raw_sha256 = hashlib.sha256(raw_content).hexdigest()
        pages = render_source(raw_content, candidate.mime_type)
        summary.pages_rendered += len(pages)

        for page in pages:
            source_object_id = opaque_id(
                self.settings.hmac_key,
                "rendered-page",
                f"{candidate.file_id}:{page.page_index}:{page.sha256}",
                prefix="src",
            )
            ingestion_key = task_ingestion_key(page.sha256)
            app_properties = {
                "dcal_schema": INGESTION_SCHEMA,
                "dcal_kind": "rendered_page",
                "dcal_sha256": page.sha256,
                "dcal_source_id": source_object_id,
                "dcal_patient_group": patient_group_id,
                "dcal_encounter_group": encounter_group_id,
                "dcal_page_index": str(page.page_index),
                "dcal_render_profile": page.render_profile,
            }
            _, created = self.drive.ensure_page(
                self.layout, page, app_properties
            )
            if created:
                summary.pages_new += 1
            else:
                summary.pages_duplicate += 1

            write_page_cache(self.settings.cache_root, page)
            task_id = task_index.get(ingestion_key)
            if task_id is None:
                task_data: dict[str, object] = {
                    "image": label_studio_local_url(page.sha256),
                    "source_object_id": source_object_id,
                    "source_sha256": page.sha256,
                    "raw_source_sha256": raw_sha256,
                    "patient_group_id": patient_group_id,
                    "encounter_group_id": encounter_group_id,
                    "writer_group_ids": [],
                    "source_page_index": page.page_index,
                    "annotation_schema_version": "dcal.annotation.v1",
                    "ingestion_schema_version": INGESTION_SCHEMA,
                    "render_profile": page.render_profile,
                    "dcal_ingestion_key": ingestion_key,
                }
                task_id = self.annotation_gateway.create_task(task_data)
                task_index[ingestion_key] = task_id
                summary.tasks_created += 1
            else:
                summary.tasks_reused += 1

            self.ledger.record_page(
                PageRecord(
                    page_sha256=page.sha256,
                    source_key=source_key,
                    source_object_id=source_object_id,
                    patient_group_id=patient_group_id,
                    encounter_group_id=encounter_group_id,
                    page_index=page.page_index,
                    local_path=page_relative_path(page.sha256).as_posix(),
                    annotation_task_id=task_id,
                )
            )

        self.drive.archive_source(
            self.layout,
            candidate,
            raw_sha256=raw_sha256,
            page_count=len(pages),
            patient_group_id=patient_group_id,
            encounter_group_id=encounter_group_id,
        )
        self.ledger.record_source(
            source_key=source_key,
            raw_sha256=raw_sha256,
            patient_group_id=patient_group_id,
            encounter_group_id=encounter_group_id,
            status="complete",
            page_count=len(pages),
        )

    def sync_once(self) -> SyncSummary:
        summary = SyncSummary()
        candidates, layout_errors = self.drive.scan_inbox(self.layout)
        summary.layout_errors = layout_errors
        task_index = self.annotation_gateway.task_index()
        for candidate in candidates:
            summary.sources_seen += 1
            patient_group_id, encounter_group_id, source_key = self._identities(candidate)
            try:
                self._process_source(candidate, task_index, summary)
                summary.sources_completed += 1
            except SourceRejected as error:
                self.drive.quarantine_source(
                    self.layout, candidate, error_code=error.code
                )
                self.ledger.record_source(
                    source_key=source_key,
                    patient_group_id=patient_group_id,
                    encounter_group_id=encounter_group_id,
                    status="quarantined",
                    error_code=error.code,
                )
                summary.sources_quarantined += 1
            except Exception:
                self.ledger.record_source(
                    source_key=source_key,
                    patient_group_id=patient_group_id,
                    encounter_group_id=encounter_group_id,
                    status="failed",
                    error_code="infrastructure_failure",
                )
                summary.sources_failed += 1
                break
        return summary
