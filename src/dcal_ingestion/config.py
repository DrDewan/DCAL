from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .identity import validate_hmac_key


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True)
class DriveRuntimeConfig:
    root_folder_id: str
    credentials_path: Path | None
    delegated_subject: str | None
    cache_root: Path
    ledger_path: Path

    @classmethod
    def from_env(cls, *, require_root: bool = True) -> "DriveRuntimeConfig":
        root = os.environ.get("DCAL_DRIVE_ROOT_FOLDER_ID", "").strip()
        if require_root and not root:
            raise ValueError("DCAL_DRIVE_ROOT_FOLDER_ID is required")
        credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        delegated = os.environ.get("GOOGLE_DELEGATED_SUBJECT", "").strip()
        return cls(
            root_folder_id=root,
            credentials_path=Path(credentials) if credentials else None,
            delegated_subject=delegated or None,
            cache_root=Path(
                os.environ.get("DCAL_PAGE_CACHE_ROOT", "/app/data/images")
            ),
            ledger_path=Path(
                os.environ.get(
                    "DCAL_INGESTION_LEDGER", "/app/data/state/ingestion.sqlite3"
                )
            ),
        )


@dataclass(frozen=True)
class SyncRuntimeConfig:
    drive: DriveRuntimeConfig
    hmac_key: bytes
    annotation_backend: str
    annotation_url: str
    annotation_token: str
    annotation_project_id: int | None

    @classmethod
    def from_env(cls) -> "SyncRuntimeConfig":
        backend = os.environ.get("DCAL_ANNOTATION_BACKEND", "workbench").strip().lower()
        if backend not in {"workbench", "label_studio"}:
            raise ValueError("DCAL_ANNOTATION_BACKEND must be workbench or label_studio")
        project_id: int | None = None
        if backend == "label_studio":
            raw_project_id = _required("DCAL_LABEL_STUDIO_PROJECT_ID")
            try:
                project_id = int(raw_project_id)
            except ValueError as error:
                raise ValueError("DCAL_LABEL_STUDIO_PROJECT_ID must be an integer") from error
            if project_id < 1:
                raise ValueError("DCAL_LABEL_STUDIO_PROJECT_ID must be positive")
            annotation_url = _required("DCAL_LABEL_STUDIO_URL")
            annotation_token = _required("LABEL_STUDIO_API_TOKEN")
        else:
            annotation_url = _required("DCAL_WORKBENCH_URL")
            annotation_token = _required("DCAL_WORKBENCH_INGEST_TOKEN")
        hmac_key = _required("DCAL_GROUP_HMAC_KEY").encode("utf-8")
        validate_hmac_key(hmac_key)
        return cls(
            drive=DriveRuntimeConfig.from_env(),
            hmac_key=hmac_key,
            annotation_backend=backend,
            annotation_url=annotation_url,
            annotation_token=annotation_token,
            annotation_project_id=project_id,
        )
