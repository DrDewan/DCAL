from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import quote

from .models import RenderedPage


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def page_relative_path(page_sha256: str) -> Path:
    if not SHA256_RE.fullmatch(page_sha256):
        raise ValueError("page SHA-256 must be 64 lowercase hexadecimal characters")
    return Path("pages") / page_sha256[:2] / f"{page_sha256}.png"


def label_studio_local_url(page_sha256: str) -> str:
    relative = page_relative_path(page_sha256).as_posix()
    return f"/data/local-files/?d={quote(relative, safe='/')}"


def write_cache_content(
    cache_root: str | Path, page_sha256: str, content: bytes
) -> Path:
    actual = hashlib.sha256(content).hexdigest()
    if actual != page_sha256:
        raise ValueError("refusing to cache content with a mismatched SHA-256")
    destination = Path(cache_root) / page_relative_path(page_sha256)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == actual:
        return destination

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{page_sha256}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, destination)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return destination


def write_page_cache(cache_root: str | Path, page: RenderedPage) -> Path:
    return write_cache_content(cache_root, page.sha256, page.content)
