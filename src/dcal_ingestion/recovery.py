from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .cache import SHA256_RE, write_cache_content
from .interfaces import DriveGateway
from .models import DriveLayout
from .render import MAX_SOURCE_BYTES


@dataclass
class AuditSummary:
    checked: int = 0
    valid: int = 0
    missing_checksum: int = 0
    checksum_mismatch: int = 0
    unlocked: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {name: int(value) for name, value in vars(self).items()}

    @property
    def successful(self) -> bool:
        return (
            self.missing_checksum == 0
            and self.checksum_mismatch == 0
            and self.unlocked == 0
            and self.failed == 0
        )


@dataclass
class RestoreSummary:
    checked: int = 0
    restored: int = 0
    already_present: int = 0
    invalid: int = 0

    def as_dict(self) -> dict[str, int]:
        return {name: int(value) for name, value in vars(self).items()}

    @property
    def successful(self) -> bool:
        return self.invalid == 0


def audit_drive(drive: DriveGateway, layout: DriveLayout) -> AuditSummary:
    summary = AuditSummary()
    for folder_id in (layout.source_archive, layout.page_store):
        for stored in drive.list_stored_files(folder_id):
            summary.checked += 1
            expected = stored.expected_sha256
            if expected is None or not SHA256_RE.fullmatch(expected):
                summary.missing_checksum += 1
                continue
            if not stored.is_read_only:
                summary.unlocked += 1
            max_bytes = min(
                MAX_SOURCE_BYTES,
                (stored.size + 1) if stored.size is not None else MAX_SOURCE_BYTES,
            )
            try:
                content = drive.download(stored.file_id, max_bytes=max_bytes)
            except Exception:
                summary.failed += 1
                continue
            if hashlib.sha256(content).hexdigest() != expected:
                summary.checksum_mismatch += 1
            else:
                summary.valid += 1
    return summary


def restore_page_cache(
    drive: DriveGateway, layout: DriveLayout, cache_root: str | Path
) -> RestoreSummary:
    summary = RestoreSummary()
    for stored in drive.list_stored_files(layout.page_store):
        summary.checked += 1
        expected = stored.expected_sha256
        if expected is None or not SHA256_RE.fullmatch(expected):
            summary.invalid += 1
            continue
        max_bytes = min(
            MAX_SOURCE_BYTES,
            (stored.size + 1) if stored.size is not None else MAX_SOURCE_BYTES,
        )
        try:
            content = drive.download(stored.file_id, max_bytes=max_bytes)
            destination = Path(cache_root) / "pages" / expected[:2] / f"{expected}.png"
            existed = destination.exists() and hashlib.sha256(
                destination.read_bytes()
            ).hexdigest() == expected
            write_cache_content(cache_root, expected, content)
        except Exception:
            summary.invalid += 1
            continue
        if existed:
            summary.already_present += 1
        else:
            summary.restored += 1
    return summary
