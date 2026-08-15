from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = 3


@dataclass(frozen=True)
class PageRecord:
    page_sha256: str
    source_key: str
    source_object_id: str
    patient_group_id: str
    encounter_group_id: str
    page_index: int
    local_path: str
    annotation_task_id: int


class IngestionLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "IngestionLedger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _migrate(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ledger_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sources (
                    source_key TEXT PRIMARY KEY,
                    raw_sha256 TEXT,
                    patient_group_id TEXT NOT NULL,
                    encounter_group_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    page_count INTEGER,
                    error_code TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS pages (
                    page_sha256 TEXT PRIMARY KEY,
                    source_object_id TEXT NOT NULL,
                    patient_group_id TEXT NOT NULL,
                    encounter_group_id TEXT NOT NULL,
                    page_index INTEGER NOT NULL,
                    local_path TEXT NOT NULL,
                    annotation_task_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS source_pages (
                    source_key TEXT NOT NULL,
                    page_index INTEGER NOT NULL,
                    page_sha256 TEXT NOT NULL,
                    source_object_id TEXT NOT NULL,
                    patient_group_id TEXT NOT NULL,
                    encounter_group_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(source_key, page_index)
                );
                """
            )
            row = self.connection.execute(
                "SELECT value FROM ledger_meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                self.connection.execute(
                    "INSERT INTO ledger_meta(key, value) VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            elif int(row["value"]) == 1:
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO source_pages(
                        source_key, page_index, page_sha256, source_object_id,
                        patient_group_id, encounter_group_id
                    )
                    SELECT
                        'legacy_' || substr(page_sha256, 1, 32), page_index,
                        page_sha256, source_object_id, patient_group_id,
                        encounter_group_id
                    FROM pages
                    """
                )
                self._migrate_task_id_column()
                self.connection.execute(
                    "UPDATE ledger_meta SET value=? WHERE key='schema_version'",
                    (str(SCHEMA_VERSION),),
                )
            elif int(row["value"]) == 2:
                self._migrate_task_id_column()
                self.connection.execute(
                    "UPDATE ledger_meta SET value=? WHERE key='schema_version'",
                    (str(SCHEMA_VERSION),),
                )
            elif int(row["value"]) != SCHEMA_VERSION:
                raise RuntimeError(
                    f"unsupported ingestion ledger schema {row['value']!r}"
                )

    def _migrate_task_id_column(self) -> None:
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(pages)")
        }
        if "annotation_task_id" in columns:
            return
        if "label_studio_task_id" not in columns:
            raise RuntimeError("ingestion ledger pages table has no task ID column")
        self.connection.executescript(
            """
            ALTER TABLE pages RENAME TO pages_v2;
            CREATE TABLE pages (
                page_sha256 TEXT PRIMARY KEY,
                source_object_id TEXT NOT NULL,
                patient_group_id TEXT NOT NULL,
                encounter_group_id TEXT NOT NULL,
                page_index INTEGER NOT NULL,
                local_path TEXT NOT NULL,
                annotation_task_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO pages(
                page_sha256, source_object_id, patient_group_id,
                encounter_group_id, page_index, local_path,
                annotation_task_id, created_at
            )
            SELECT
                page_sha256, source_object_id, patient_group_id,
                encounter_group_id, page_index, local_path,
                label_studio_task_id, created_at
            FROM pages_v2;
            DROP TABLE pages_v2;
            """
        )

    def page(self, page_sha256: str) -> PageRecord | None:
        row = self.connection.execute(
            """
            SELECT
                pages.page_sha256,
                pages.local_path,
                pages.annotation_task_id,
                source_pages.source_key,
                source_pages.source_object_id,
                source_pages.patient_group_id,
                source_pages.encounter_group_id,
                source_pages.page_index
            FROM pages
            JOIN source_pages USING(page_sha256)
            WHERE pages.page_sha256=?
            ORDER BY source_pages.created_at, source_pages.source_key
            LIMIT 1
            """,
            (page_sha256,),
        ).fetchone()
        if row is None:
            return None
        return PageRecord(
            page_sha256=row["page_sha256"],
            source_key=row["source_key"],
            source_object_id=row["source_object_id"],
            patient_group_id=row["patient_group_id"],
            encounter_group_id=row["encounter_group_id"],
            page_index=row["page_index"],
            local_path=row["local_path"],
            annotation_task_id=row["annotation_task_id"],
        )

    def record_page(self, record: PageRecord) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO pages(
                    page_sha256, source_object_id, patient_group_id,
                    encounter_group_id, page_index, local_path,
                    annotation_task_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(page_sha256) DO UPDATE SET
                    local_path=excluded.local_path,
                    annotation_task_id=excluded.annotation_task_id
                """,
                (
                    record.page_sha256,
                    record.source_object_id,
                    record.patient_group_id,
                    record.encounter_group_id,
                    record.page_index,
                    record.local_path,
                    record.annotation_task_id,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO source_pages(
                    source_key, page_index, page_sha256, source_object_id,
                    patient_group_id, encounter_group_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key, page_index) DO UPDATE SET
                    page_sha256=excluded.page_sha256,
                    source_object_id=excluded.source_object_id,
                    patient_group_id=excluded.patient_group_id,
                    encounter_group_id=excluded.encounter_group_id
                """,
                (
                    record.source_key,
                    record.page_index,
                    record.page_sha256,
                    record.source_object_id,
                    record.patient_group_id,
                    record.encounter_group_id,
                ),
            )

    def record_source(
        self,
        *,
        source_key: str,
        patient_group_id: str,
        encounter_group_id: str,
        status: str,
        raw_sha256: str | None = None,
        page_count: int | None = None,
        error_code: str | None = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO sources(
                    source_key, raw_sha256, patient_group_id, encounter_group_id,
                    status, page_count, error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    raw_sha256=excluded.raw_sha256,
                    status=excluded.status,
                    page_count=excluded.page_count,
                    error_code=excluded.error_code,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    source_key,
                    raw_sha256,
                    patient_group_id,
                    encounter_group_id,
                    status,
                    page_count,
                    error_code,
                ),
            )
