from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

from .models import (
    DRIVE_LAYOUT_SCHEMA,
    INGESTION_SCHEMA,
    DriveContractError,
    DriveLayout,
    IngestionCandidate,
    RenderedPage,
    SourceRejected,
    StoredDriveFile,
)


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
GOOGLE_NATIVE_PREFIX = "application/vnd.google-apps."
FILE_FIELDS = (
    "id,name,mimeType,size,parents,appProperties,contentRestrictions,"
    "capabilities(canEdit,canDownload),driveId"
)
MAX_DRIVE_OBJECT_BYTES = 250 * 1024 * 1024

LAYOUT_FOLDERS = {
    "inbox": ("00_INBOX", "inbox"),
    "source_archive": ("10_SOURCE_ARCHIVE", "source_archive"),
    "page_store": ("20_PAGE_STORE", "page_store"),
    "quarantine": ("30_QUARANTINE", "quarantine"),
    "dataset_exports": ("40_DATASET_EXPORTS", "dataset_exports"),
    "manifests": ("90_MANIFESTS", "manifests"),
}


def _safe_extension(mime_type: str) -> str:
    return {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/tiff": ".tiff",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
    }.get(mime_type, ".bin")


def _stored_file(payload: dict[str, Any]) -> StoredDriveFile:
    raw_size = payload.get("size")
    size = int(raw_size) if isinstance(raw_size, (int, str)) and str(raw_size).isdigit() else None
    restrictions = payload.get("contentRestrictions") or []
    return StoredDriveFile(
        file_id=str(payload["id"]),
        mime_type=str(payload.get("mimeType") or "application/octet-stream"),
        size=size,
        app_properties={
            str(key): str(value)
            for key, value in (payload.get("appProperties") or {}).items()
        },
        content_restrictions=tuple(
            item for item in restrictions if isinstance(item, dict)
        ),
    )


class GoogleDriveGateway:
    def __init__(self, service: Any):
        self.service = service

    @classmethod
    def from_credentials(
        cls,
        credentials_path: str | Path | None,
        *,
        delegated_subject: str | None = None,
    ) -> "GoogleDriveGateway":
        try:
            import google.auth
            from googleapiclient.discovery import build
        except ImportError as error:
            raise RuntimeError(
                "Google Drive dependencies are missing; install the DCAL package"
            ) from error

        if credentials_path:
            credentials, _ = google.auth.load_credentials_from_file(
                str(credentials_path), scopes=[DRIVE_SCOPE]
            )
        else:
            credentials, _ = google.auth.default(scopes=[DRIVE_SCOPE])
        if delegated_subject:
            with_subject = getattr(credentials, "with_subject", None)
            if with_subject is None:
                raise ValueError(
                    "GOOGLE_DELEGATED_SUBJECT requires service-account credentials"
                )
            credentials = with_subject(delegated_subject)
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return cls(service)

    def _list_query(self, query: str) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        token: str | None = None
        while True:
            response = (
                self.service.files()
                .list(
                    q=query,
                    pageSize=1000,
                    pageToken=token,
                    spaces="drive",
                    fields=f"nextPageToken,files({FILE_FIELDS})",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            raw_files = response.get("files", [])
            if not isinstance(raw_files, list):
                raise DriveContractError("Drive returned an invalid file list")
            files.extend(item for item in raw_files if isinstance(item, dict))
            token = response.get("nextPageToken")
            if not token:
                return files

    def _list_children(self, parent_id: str) -> list[dict[str, Any]]:
        return self._list_query(f"'{parent_id}' in parents and trashed = false")

    def _update_properties(self, file_id: str, properties: dict[str, str]) -> None:
        (
            self.service.files()
            .update(
                fileId=file_id,
                body={"appProperties": properties},
                supportsAllDrives=True,
                fields=FILE_FIELDS,
            )
            .execute()
        )

    def _ensure_folder(self, root_id: str, name: str, role: str) -> str:
        children = self._list_children(root_id)
        by_role = [
            item
            for item in children
            if item.get("mimeType") == FOLDER_MIME_TYPE
            and (item.get("appProperties") or {}).get("dcal_role") == role
        ]
        if len(by_role) > 1:
            raise DriveContractError(f"multiple Drive folders declare role {role!r}")
        if by_role:
            return str(by_role[0]["id"])

        by_name = [
            item
            for item in children
            if item.get("mimeType") == FOLDER_MIME_TYPE and item.get("name") == name
        ]
        if len(by_name) > 1:
            raise DriveContractError(f"multiple Drive folders are named {name!r}")
        properties = {
            "dcal_schema": DRIVE_LAYOUT_SCHEMA,
            "dcal_role": role,
        }
        if by_name:
            folder_id = str(by_name[0]["id"])
            self._update_properties(folder_id, properties)
            return folder_id

        created = (
            self.service.files()
            .create(
                body={
                    "name": name,
                    "mimeType": FOLDER_MIME_TYPE,
                    "parents": [root_id],
                    "appProperties": properties,
                },
                supportsAllDrives=True,
                fields=FILE_FIELDS,
            )
            .execute()
        )
        return str(created["id"])

    def bootstrap_layout(self, root_folder_id: str) -> DriveLayout:
        if not root_folder_id:
            raise ValueError("Drive root folder ID is required")
        values = {
            attribute: self._ensure_folder(root_folder_id, name, role)
            for attribute, (name, role) in LAYOUT_FOLDERS.items()
        }
        return DriveLayout(root=root_folder_id, **values)

    def resolve_layout(self, root_folder_id: str) -> DriveLayout:
        children = self._list_children(root_folder_id)
        values: dict[str, str] = {}
        for attribute, (_, role) in LAYOUT_FOLDERS.items():
            matches = [
                item
                for item in children
                if item.get("mimeType") == FOLDER_MIME_TYPE
                and (item.get("appProperties") or {}).get("dcal_role") == role
            ]
            if len(matches) != 1:
                raise DriveContractError(
                    f"Drive root must contain exactly one folder with role {role!r}"
                )
            values[attribute] = str(matches[0]["id"])
        return DriveLayout(root=root_folder_id, **values)

    def scan_inbox(
        self, layout: DriveLayout
    ) -> tuple[list[IngestionCandidate], int]:
        candidates: list[IngestionCandidate] = []
        layout_errors = 0
        for patient in self._list_children(layout.inbox):
            if patient.get("mimeType") != FOLDER_MIME_TYPE:
                layout_errors += 1
                continue
            patient_id = str(patient["id"])
            for encounter in self._list_children(patient_id):
                if encounter.get("mimeType") != FOLDER_MIME_TYPE:
                    layout_errors += 1
                    continue
                encounter_id = str(encounter["id"])
                for source in self._list_children(encounter_id):
                    if source.get("mimeType") == FOLDER_MIME_TYPE:
                        layout_errors += 1
                        continue
                    mime_type = str(source.get("mimeType") or "")
                    if mime_type.startswith(GOOGLE_NATIVE_PREFIX):
                        mime_type = "application/vnd.google-apps.unsupported"
                    raw_size = source.get("size")
                    size = (
                        int(raw_size)
                        if isinstance(raw_size, (int, str)) and str(raw_size).isdigit()
                        else None
                    )
                    candidates.append(
                        IngestionCandidate(
                            file_id=str(source["id"]),
                            parent_id=encounter_id,
                            patient_folder_id=patient_id,
                            encounter_folder_id=encounter_id,
                            mime_type=mime_type,
                            name=str(source.get("name") or "source"),
                            size=size,
                            app_properties={
                                str(key): str(value)
                                for key, value in (
                                    source.get("appProperties") or {}
                                ).items()
                            },
                        )
                    )
        return candidates, layout_errors

    def download(self, file_id: str, *, max_bytes: int) -> bytes:
        try:
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError as error:
            raise RuntimeError("Google Drive dependencies are missing") from error

        target = io.BytesIO()
        request = self.service.files().get_media(
            fileId=file_id, supportsAllDrives=True
        )
        downloader = MediaIoBaseDownload(target, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
            if target.tell() > max_bytes:
                raise SourceRejected(
                    "source_too_large",
                    f"source exceeds the {max_bytes // (1024 * 1024)} MiB safety limit",
                )
        return target.getvalue()

    def _lock(self, file_id: str) -> dict[str, Any]:
        return (
            self.service.files()
            .update(
                fileId=file_id,
                body={
                    "contentRestrictions": [
                        {
                            "readOnly": True,
                            "ownerRestricted": True,
                            "reason": "DCAL checksum-verified archive object.",
                        }
                    ]
                },
                supportsAllDrives=True,
                fields=FILE_FIELDS,
            )
            .execute()
        )

    def ensure_page(
        self,
        layout: DriveLayout,
        page: RenderedPage,
        app_properties: dict[str, str],
    ) -> tuple[StoredDriveFile, bool]:
        matches = self._list_query(
            f"'{layout.page_store}' in parents and trashed = false and "
            f"appProperties has {{ key='dcal_sha256' and value='{page.sha256}' }}"
        )
        if len(matches) > 1:
            raise DriveContractError(
                f"multiple page-store objects claim SHA-256 {page.sha256}"
            )
        if matches:
            existing = _stored_file(matches[0])
            try:
                downloaded = self.download(
                    existing.file_id, max_bytes=MAX_DRIVE_OBJECT_BYTES
                )
            except SourceRejected as error:
                raise DriveContractError("page-store object exceeds safety limit") from error
            if hashlib.sha256(downloaded).hexdigest() != page.sha256:
                raise DriveContractError("page-store checksum mismatch")
            if not existing.is_read_only:
                existing = _stored_file(self._lock(existing.file_id))
            return existing, False

        try:
            from googleapiclient.http import MediaIoBaseUpload
        except ImportError as error:
            raise RuntimeError("Google Drive dependencies are missing") from error
        media = MediaIoBaseUpload(
            io.BytesIO(page.content),
            mimetype=page.mime_type,
            resumable=True,
            chunksize=8 * 1024 * 1024,
        )
        created = (
            self.service.files()
            .create(
                body={
                    "name": f"{page.sha256}.png",
                    "mimeType": page.mime_type,
                    "parents": [layout.page_store],
                    "appProperties": app_properties,
                },
                media_body=media,
                supportsAllDrives=True,
                fields=FILE_FIELDS,
            )
            .execute()
        )
        locked = self._lock(str(created["id"]))
        return _stored_file(locked), True

    def archive_source(
        self,
        layout: DriveLayout,
        candidate: IngestionCandidate,
        *,
        raw_sha256: str,
        page_count: int,
        patient_group_id: str,
        encounter_group_id: str,
    ) -> None:
        properties = {
            "dcal_schema": INGESTION_SCHEMA,
            "dcal_kind": "raw_source",
            "dcal_sha256": raw_sha256,
            "dcal_patient_group": patient_group_id,
            "dcal_encounter_group": encounter_group_id,
            "dcal_page_count": str(page_count),
            "dcal_ingestion_status": "complete",
        }
        (
            self.service.files()
            .update(
                fileId=candidate.file_id,
                addParents=layout.source_archive,
                removeParents=candidate.parent_id,
                body={
                    "name": f"{raw_sha256}{_safe_extension(candidate.mime_type)}",
                    "appProperties": properties,
                },
                supportsAllDrives=True,
                fields=FILE_FIELDS,
            )
            .execute()
        )
        try:
            self._lock(candidate.file_id)
        except Exception:
            # Drive has no transaction spanning move + content restriction. Put the
            # source back into its encounter folder so the next sync can reconcile.
            try:
                (
                    self.service.files()
                    .update(
                        fileId=candidate.file_id,
                        addParents=candidate.parent_id,
                        removeParents=layout.source_archive,
                        body={
                            "name": candidate.name,
                            "appProperties": candidate.app_properties,
                        },
                        supportsAllDrives=True,
                        fields=FILE_FIELDS,
                    )
                    .execute()
                )
            finally:
                raise

    def quarantine_source(
        self,
        layout: DriveLayout,
        candidate: IngestionCandidate,
        *,
        error_code: str,
    ) -> None:
        (
            self.service.files()
            .update(
                fileId=candidate.file_id,
                addParents=layout.quarantine,
                removeParents=candidate.parent_id,
                body={
                    "appProperties": {
                        "dcal_schema": INGESTION_SCHEMA,
                        "dcal_ingestion_status": "quarantined",
                        "dcal_error_code": error_code[:100],
                    }
                },
                supportsAllDrives=True,
                fields=FILE_FIELDS,
            )
            .execute()
        )

    def list_stored_files(self, folder_id: str) -> list[StoredDriveFile]:
        return [
            _stored_file(item)
            for item in self._list_children(folder_id)
            if item.get("mimeType") != FOLDER_MIME_TYPE
        ]
