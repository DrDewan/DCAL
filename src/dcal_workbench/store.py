from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

from PIL import Image

from dcal_annotations.taxonomy import Taxonomy
from dcal_ingestion.cache import page_relative_path, write_cache_content
from dcal_ingestion.identity import task_ingestion_key
from dcal_ingestion.models import INGESTION_SCHEMA, RENDER_PROFILE
from dcal_ingestion.render import render_source


WORKBENCH_SCHEMA = "dcal.workbench.v1"
ANNOTATION_SCHEMA = "dcal.annotation.v2"
GOLD_SCHEMA = "dcal.gold.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
INGESTION_KEY_RE = re.compile(r"^task_[0-9a-f]{32}$")
FIELD_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
TASK_STATUSES = {"unassigned", "in_progress", "completed", "needs_review"}
CONTENT_PROFILES = {
    "printed_blank_form",
    "printed_filled_form",
    "printed_document",
    "printed_with_handwriting",
    "handwritten_page",
    "unknown",
}
NON_REGION_DOCUMENTS = {
    "blank_or_noninformative_page",
    "duplicate_or_rephotographed_source",
    "non_clinical_cover",
    "unknown_document",
}


class WorkbenchError(ValueError):
    """Safe validation error that never includes document contents."""


class VersionConflict(WorkbenchError):
    """The task changed after a client loaded it."""


class TaskNotFound(WorkbenchError):
    """The requested task does not exist."""


@dataclass(frozen=True)
class UploadItem:
    content: bytes
    mime_type: str


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _public_task_id(value: int) -> str:
    return f"page_{value:06d}"


def _numeric_task_id(value: str | int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"page_[0-9]{6,}", value):
        return int(value.split("_", 1)[1])
    raise TaskNotFound("task not found")


def _safe_local_path(image_uri: str, sha256: str) -> str:
    parsed = urlparse(image_uri)
    values = parse_qs(parsed.query).get("d", [])
    raw = values[0] if values else parsed.path.lstrip("/")
    if raw.startswith("data/local-files/"):
        raw = raw.removeprefix("data/local-files/")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise WorkbenchError("task image path is unsafe")
    expected = page_relative_path(sha256).as_posix()
    if path.as_posix() != expected:
        raise WorkbenchError("task image path does not match its checksum")
    return expected


class WorkbenchStore:
    def __init__(self, database_path: str | Path, cache_root: str | Path, taxonomy_path: str | Path):
        self.database_path = Path(database_path)
        self.cache_root = Path(cache_root)
        self.taxonomy_path = Path(taxonomy_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.taxonomy = Taxonomy.from_path(self.taxonomy_path)
        self._taxonomy_payload = json.loads(self.taxonomy_path.read_text(encoding="utf-8"))
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _migrate(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workbench_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ingestion_key TEXT NOT NULL UNIQUE,
                    source_origin TEXT NOT NULL,
                    dataset_eligible INTEGER NOT NULL DEFAULT 0,
                    source_object_id TEXT,
                    source_sha256 TEXT NOT NULL UNIQUE,
                    raw_source_sha256 TEXT,
                    patient_group_id TEXT,
                    encounter_group_id TEXT,
                    writer_group_ids_json TEXT NOT NULL DEFAULT '[]',
                    source_page_index INTEGER NOT NULL,
                    ingestion_schema_version TEXT,
                    render_profile TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    image_width INTEGER NOT NULL,
                    image_height INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'unassigned',
                    assigned_to TEXT,
                    annotation_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id),
                    version INTEGER NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    annotation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_id, version)
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_tasks_document_type
                    ON tasks(json_extract(annotation_json, '$.document_type'));
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO workbench_meta(key, value) VALUES('schema_version', '1')"
            )

    def taxonomy_payload(self) -> dict[str, Any]:
        return {
            **self._taxonomy_payload,
            "workbench_schema_version": WORKBENCH_SCHEMA,
            "annotation_schema_version": ANNOTATION_SCHEMA,
            "content_profiles": [
                {"code": "printed_blank_form", "name": "Blank printed form"},
                {"code": "printed_filled_form", "name": "Printed form with typed values"},
                {"code": "printed_document", "name": "Fully printed document"},
                {"code": "printed_with_handwriting", "name": "Printed form with handwriting"},
                {"code": "handwritten_page", "name": "Primarily handwritten page"},
                {"code": "unknown", "name": "Not sure"},
            ],
        }

    @staticmethod
    def _blank_annotation() -> dict[str, Any]:
        return {
            "schema_version": ANNOTATION_SCHEMA,
            "document_type": None,
            "document_variant": None,
            "content_profile": None,
            "image_quality": [],
            "notes": "",
            "regions": [],
        }

    def _image_size(self, local_path: str) -> tuple[int, int]:
        path = (self.cache_root / local_path).resolve()
        root = self.cache_root.resolve()
        if root not in path.parents or not path.is_file():
            raise WorkbenchError("task image is not present in the private cache")
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
        if width < 1 or height < 1:
            raise WorkbenchError("task image has invalid dimensions")
        return width, height

    def import_ingestion_task(self, data: dict[str, Any]) -> tuple[int, bool]:
        required_strings = (
            "image",
            "source_object_id",
            "source_sha256",
            "raw_source_sha256",
            "patient_group_id",
            "encounter_group_id",
            "annotation_schema_version",
            "ingestion_schema_version",
            "render_profile",
            "dcal_ingestion_key",
        )
        for name in required_strings:
            if not isinstance(data.get(name), str) or not data[name].strip():
                raise WorkbenchError(f"ingestion task is missing {name}")
        sha256 = data["source_sha256"]
        raw_sha256 = data["raw_source_sha256"]
        ingestion_key = data["dcal_ingestion_key"]
        if not SHA256_RE.fullmatch(sha256) or not SHA256_RE.fullmatch(raw_sha256):
            raise WorkbenchError("ingestion task contains an invalid checksum")
        if not INGESTION_KEY_RE.fullmatch(ingestion_key):
            raise WorkbenchError("ingestion task contains an invalid key")
        if ingestion_key != task_ingestion_key(sha256):
            raise WorkbenchError("ingestion key does not match page checksum")
        if data["ingestion_schema_version"] != INGESTION_SCHEMA:
            raise WorkbenchError("unsupported ingestion schema")
        if data["annotation_schema_version"] != "dcal.annotation.v1":
            raise WorkbenchError("unsupported ingestion annotation schema")
        page_index = data.get("source_page_index")
        if isinstance(page_index, bool) or not isinstance(page_index, int) or page_index < 1:
            raise WorkbenchError("source_page_index must be a positive integer")
        writer_groups = data.get("writer_group_ids", [])
        if not isinstance(writer_groups, list) or not all(
            isinstance(item, str) and item for item in writer_groups
        ):
            raise WorkbenchError("writer_group_ids must be an array of opaque strings")
        local_path = _safe_local_path(data["image"], sha256)
        width, height = self._image_size(local_path)
        now = _now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id, dataset_eligible FROM tasks WHERE ingestion_key=?",
                (ingestion_key,),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    """
                    UPDATE tasks SET
                        source_origin='google_drive', dataset_eligible=1,
                        source_object_id=?, raw_source_sha256=?, patient_group_id=?,
                        encounter_group_id=?, writer_group_ids_json=?,
                        source_page_index=?, ingestion_schema_version=?,
                        render_profile=?, local_path=?, image_width=?, image_height=?,
                        updated_at=?
                    WHERE id=?
                    """,
                    (
                        data["source_object_id"], raw_sha256,
                        data["patient_group_id"], data["encounter_group_id"],
                        _json(writer_groups), page_index, data["ingestion_schema_version"],
                        data["render_profile"], local_path, width, height, now,
                        existing["id"],
                    ),
                )
                return int(existing["id"]), False
            cursor = connection.execute(
                """
                INSERT INTO tasks(
                    ingestion_key, source_origin, dataset_eligible, source_object_id,
                    source_sha256, raw_source_sha256, patient_group_id,
                    encounter_group_id, writer_group_ids_json, source_page_index,
                    ingestion_schema_version, render_profile, local_path,
                    image_width, image_height, annotation_json, created_at, updated_at
                ) VALUES (?, 'google_drive', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ingestion_key, data["source_object_id"], sha256, raw_sha256,
                    data["patient_group_id"], data["encounter_group_id"],
                    _json(writer_groups), page_index, data["ingestion_schema_version"],
                    data["render_profile"], local_path, width, height,
                    _json(self._blank_annotation()), now, now,
                ),
            )
            return int(cursor.lastrowid), True

    def upload_sources(self, sources: Iterable[UploadItem]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for source in sources:
            raw_sha256 = hashlib.sha256(source.content).hexdigest()
            pages = render_source(source.content, source.mime_type)
            for page in pages:
                local_path = page_relative_path(page.sha256).as_posix()
                write_cache_content(self.cache_root, page.sha256, page.content)
                ingestion_key = task_ingestion_key(page.sha256)
                now = _now()
                with self._connect() as connection:
                    existing = connection.execute(
                        "SELECT id, dataset_eligible FROM tasks WHERE ingestion_key=?",
                        (ingestion_key,),
                    ).fetchone()
                    if existing is not None:
                        task_id = int(existing["id"])
                        dataset_eligible = bool(existing["dataset_eligible"])
                        created = False
                    else:
                        cursor = connection.execute(
                            """
                            INSERT INTO tasks(
                                ingestion_key, source_origin, dataset_eligible,
                                source_object_id, source_sha256, raw_source_sha256,
                                source_page_index, render_profile, local_path,
                                image_width, image_height, annotation_json,
                                created_at, updated_at
                            ) VALUES (?, 'manual_upload', 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                ingestion_key, f"manual_{page.sha256[:32]}", page.sha256,
                                raw_sha256, page.page_index, page.render_profile, local_path,
                                page.width, page.height, _json(self._blank_annotation()), now, now,
                            ),
                        )
                        task_id = int(cursor.lastrowid)
                        dataset_eligible = False
                        created = True
                results.append(
                    {
                        "id": _public_task_id(task_id),
                        "created": created,
                        "dataset_eligible": dataset_eligible,
                    }
                )
        return results

    def task_index(self) -> dict[str, int]:
        with self._connect() as connection:
            return {
                row["ingestion_key"]: int(row["id"])
                for row in connection.execute("SELECT id, ingestion_key FROM tasks")
            }

    def _summary(self, row: sqlite3.Row) -> dict[str, Any]:
        annotation = json.loads(row["annotation_json"])
        return {
            "id": _public_task_id(row["id"]),
            "status": row["status"],
            "assigned_to": row["assigned_to"],
            "document_type": annotation.get("document_type"),
            "content_profile": annotation.get("content_profile"),
            "region_count": len(annotation.get("regions", [])),
            "dataset_eligible": bool(row["dataset_eligible"]),
            "source_origin": row["source_origin"],
            "updated_at": row["updated_at"],
            "version": row["version"],
        }

    def list_tasks(
        self,
        *,
        status: str | None = None,
        document_type: str | None = None,
        query: str | None = None,
        limit: int = 250,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        values: list[Any] = []
        if status:
            if status not in TASK_STATUSES:
                raise WorkbenchError("unknown status filter")
            clauses.append("status=?")
            values.append(status)
        if document_type:
            clauses.append("json_extract(annotation_json, '$.document_type')=?")
            values.append(document_type)
        if query:
            cleaned = query.strip().lower()
            if cleaned:
                clauses.append("(lower(assigned_to) LIKE ? OR printf('page_%06d', id) LIKE ?)")
                values.extend((f"%{cleaned}%", f"%{cleaned}%"))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM tasks {where} ORDER BY updated_at DESC, id DESC LIMIT ?",
                (*values, min(max(limit, 1), 1000)),
            ).fetchall()
            counts = {
                row["status"]: row["count"]
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"
                )
            }
            total = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            eligible = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE dataset_eligible=1"
            ).fetchone()[0]
        return {
            "tasks": [self._summary(row) for row in rows],
            "counts": {name: int(counts.get(name, 0)) for name in sorted(TASK_STATUSES)},
            "total": int(total),
            "dataset_eligible": int(eligible),
        }

    def get_task(self, task_id: str | int) -> dict[str, Any]:
        numeric_id = _numeric_task_id(task_id)
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id=?", (numeric_id,)).fetchone()
        if row is None:
            raise TaskNotFound("task not found")
        annotation = json.loads(row["annotation_json"])
        return {
            **self._summary(row),
            "image": {
                "url": f"/api/tasks/{_public_task_id(row['id'])}/image",
                "width": row["image_width"],
                "height": row["image_height"],
            },
            "annotation": annotation,
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    def image_path(self, task_id: str | int) -> Path:
        numeric_id = _numeric_task_id(task_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT local_path FROM tasks WHERE id=?", (numeric_id,)
            ).fetchone()
        if row is None:
            raise TaskNotFound("task not found")
        path = (self.cache_root / row["local_path"]).resolve()
        root = self.cache_root.resolve()
        if root not in path.parents or not path.is_file():
            raise TaskNotFound("task image is unavailable")
        return path

    def _validate_annotation(self, annotation: Any, *, completing: bool) -> dict[str, Any]:
        if not isinstance(annotation, dict):
            raise WorkbenchError("annotation must be an object")
        document_type = annotation.get("document_type")
        if (
            document_type is not None
            and document_type not in self.taxonomy.physical_document_types
        ):
            raise WorkbenchError("unknown physical document type")
        variant = annotation.get("document_variant")
        if variant is not None:
            contract = self.taxonomy.physical_document_variants.get(variant)
            if contract is None:
                raise WorkbenchError("unknown physical document variant")
            if document_type and contract.get("physical_document_type") != document_type:
                raise WorkbenchError("document variant does not belong to physical type")
        content_profile = annotation.get("content_profile")
        if content_profile is not None and content_profile not in CONTENT_PROFILES:
            raise WorkbenchError("unknown page content profile")
        quality = annotation.get("image_quality", [])
        if not isinstance(quality, list) or len(set(quality)) != len(quality):
            raise WorkbenchError("image quality must be a unique array")
        if any(item not in self.taxonomy.image_quality_flags for item in quality):
            raise WorkbenchError("unknown image quality flag")
        if "clear" in quality and len(quality) > 1:
            raise WorkbenchError("clear cannot be combined with an image defect")
        notes = annotation.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise WorkbenchError("notes must contain at most 4000 characters")
        raw_regions = annotation.get("regions", [])
        if not isinstance(raw_regions, list):
            raise WorkbenchError("regions must be an array")
        regions: list[dict[str, Any]] = []
        ids: set[str] = set()
        orders: set[int] = set()
        for index, raw in enumerate(raw_regions):
            if not isinstance(raw, dict):
                raise WorkbenchError(f"region {index + 1} must be an object")
            region_id = raw.get("id")
            if not isinstance(region_id, str) or not re.fullmatch(r"reg_[a-f0-9]{12,32}", region_id):
                raise WorkbenchError(f"region {index + 1} has an invalid ID")
            if region_id in ids:
                raise WorkbenchError("region IDs must be unique")
            ids.add(region_id)
            label = raw.get("label")
            if label not in self.taxonomy.region_labels:
                raise WorkbenchError(f"region {index + 1} has an unknown label")
            structure_role = raw.get("structure_role", "none")
            if structure_role not in self.taxonomy.structure_roles:
                raise WorkbenchError(f"region {index + 1} has an unknown structure role")
            legibility = raw.get("legibility")
            if legibility not in self.taxonomy.legibility_states:
                raise WorkbenchError(f"region {index + 1} has an unknown legibility")
            reading_order = raw.get("reading_order")
            if isinstance(reading_order, bool) or not isinstance(reading_order, int) or reading_order < 1:
                raise WorkbenchError(f"region {index + 1} needs a positive reading order")
            if reading_order in orders:
                raise WorkbenchError("reading orders must be unique")
            orders.add(reading_order)
            geometry: dict[str, float] = {}
            for name in ("x", "y", "width", "height"):
                value = raw.get(name)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise WorkbenchError(f"region {index + 1} has invalid geometry")
                geometry[name] = round(float(value), 6)
            if not (0 <= geometry["x"] < 100 and 0 <= geometry["y"] < 100):
                raise WorkbenchError(f"region {index + 1} starts outside the page")
            if geometry["width"] <= 0 or geometry["height"] <= 0:
                raise WorkbenchError(f"region {index + 1} has no area")
            if geometry["x"] + geometry["width"] > 100.001 or geometry["y"] + geometry["height"] > 100.001:
                raise WorkbenchError(f"region {index + 1} extends outside the page")
            transcription = raw.get("transcription", "")
            if not isinstance(transcription, str) or len(transcription) > 10000:
                raise WorkbenchError(f"region {index + 1} has invalid transcription")
            field_code = raw.get("field_code", "")
            if not isinstance(field_code, str) or len(field_code) > 100:
                raise WorkbenchError(f"region {index + 1} has invalid field code")
            field_code = field_code.strip()
            if field_code and not FIELD_CODE_RE.fullmatch(field_code):
                raise WorkbenchError("field codes must use lowercase snake_case")
            label_contract = self.taxonomy.region_labels[label]
            if label_contract.get("textual") and legibility == "not_applicable":
                raise WorkbenchError(f"region {index + 1} is text and needs legibility")
            if legibility in {"illegible", "not_applicable"} and transcription.strip():
                raise WorkbenchError(f"region {index + 1} cannot contain a transcription")
            if (
                completing
                and label_contract.get("requires_transcription_when_readable")
                and legibility in {"legible", "partially_legible"}
                and not transcription.strip()
            ):
                raise WorkbenchError(f"region {index + 1} needs exact transcription")
            regions.append(
                {
                    "id": region_id,
                    "label": label,
                    "structure_role": structure_role,
                    "legibility": legibility,
                    "reading_order": reading_order,
                    "field_code": field_code or None,
                    "transcription": transcription,
                    **geometry,
                }
            )
        if completing:
            if not document_type:
                raise WorkbenchError("select the physical document type before completing")
            if not content_profile:
                raise WorkbenchError("select the page content profile before completing")
            if document_type not in NON_REGION_DOCUMENTS and not regions:
                raise WorkbenchError("clinical pages need at least one annotated region")
        return {
            "schema_version": ANNOTATION_SCHEMA,
            "document_type": document_type,
            "document_variant": variant,
            "content_profile": content_profile,
            "image_quality": quality,
            "notes": notes,
            "regions": sorted(regions, key=lambda item: item["reading_order"]),
        }

    def save_task(
        self,
        task_id: str | int,
        *,
        annotation: Any,
        expected_version: int,
        actor: str,
        status: str | None = None,
    ) -> dict[str, Any]:
        numeric_id = _numeric_task_id(task_id)
        if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 100:
            raise WorkbenchError("enter an annotator name")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise WorkbenchError("expected_version must be an integer")
        if status is not None and status not in TASK_STATUSES:
            raise WorkbenchError("unknown task status")
        completing = status == "completed"
        normalized = self._validate_annotation(annotation, completing=completing)
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT version, status FROM tasks WHERE id=?", (numeric_id,)
            ).fetchone()
            if row is None:
                raise TaskNotFound("task not found")
            if int(row["version"]) != expected_version:
                raise VersionConflict("this page was changed elsewhere; reload before saving")
            next_version = expected_version + 1
            next_status = status or (
                "in_progress"
                if row["status"] in {"unassigned", "completed"}
                else row["status"]
            )
            completed_at = now if next_status == "completed" else None
            connection.execute(
                """
                UPDATE tasks SET annotation_json=?, status=?, assigned_to=?, version=?,
                    updated_at=?, completed_at=? WHERE id=?
                """,
                (
                    _json(normalized), next_status, actor.strip(), next_version,
                    now, completed_at, numeric_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO revisions(task_id, version, actor, action, annotation_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    numeric_id, next_version, actor.strip(),
                    "complete" if completing else "save", _json(normalized), now,
                ),
            )
        return self.get_task(numeric_id)

    def export_gold(self) -> tuple[str, dict[str, int]]:
        records: list[str] = []
        skipped_ineligible = 0
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks WHERE status='completed' ORDER BY source_sha256"
            ).fetchall()
        for row in rows:
            if not row["dataset_eligible"]:
                skipped_ineligible += 1
                continue
            annotation = self._validate_annotation(json.loads(row["annotation_json"]), completing=True)
            record: dict[str, Any] = {
                "schema_version": GOLD_SCHEMA,
                "taxonomy_version": self._taxonomy_payload["schema_version"],
                "source": {
                    "object_id": row["source_object_id"],
                    "sha256": row["source_sha256"],
                    "patient_group_id": row["patient_group_id"],
                    "encounter_group_id": row["encounter_group_id"],
                    "writer_group_ids": json.loads(row["writer_group_ids_json"]),
                    "page_index": row["source_page_index"],
                    "ingestion": {
                        "raw_sha256": row["raw_source_sha256"],
                        "schema_version": row["ingestion_schema_version"],
                        "render_profile": row["render_profile"],
                        "task_key": row["ingestion_key"],
                    },
                },
                "annotation": {
                    "source": "dcal_workbench",
                    "workbench_task_id": _public_task_id(row["id"]),
                    "annotator": row["assigned_to"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                },
                "classification": {
                    "physical_document_type": annotation["document_type"],
                    "physical_document_variant": annotation["document_variant"],
                    "content_profile": annotation["content_profile"],
                },
                "image_quality": annotation["image_quality"],
                "regions": [
                    {
                        "region_id": region["id"],
                        "reading_order": region["reading_order"],
                        "label": region["label"],
                        "structure_role": region["structure_role"],
                        "legibility": region["legibility"],
                        "semantic_region_type": None,
                        "field_code": region["field_code"],
                        "transcription": region["transcription"] or None,
                        "geometry": {
                            "x": region["x"], "y": region["y"],
                            "width": region["width"], "height": region["height"],
                            "rotation": 0.0,
                            "original_width": row["image_width"],
                            "original_height": row["image_height"],
                            "image_rotation": 0.0,
                        },
                    }
                    for region in annotation["regions"]
                ],
            }
            digest = hashlib.sha256(_json(record).encode("utf-8")).hexdigest()
            record["record_sha256"] = digest
            records.append(_json(record))
        content = "\n".join(records) + ("\n" if records else "")
        return content, {
            "exported": len(records),
            "skipped_manual_without_grouping": skipped_ineligible,
        }
