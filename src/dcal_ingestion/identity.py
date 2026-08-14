from __future__ import annotations

import base64
import hashlib
import hmac


MINIMUM_HMAC_KEY_BYTES = 32


def validate_hmac_key(key: bytes) -> bytes:
    if len(key) < MINIMUM_HMAC_KEY_BYTES:
        raise ValueError(
            f"DCAL_GROUP_HMAC_KEY must contain at least {MINIMUM_HMAC_KEY_BYTES} bytes"
        )
    lowered = key.lower()
    if b"replace" in lowered or b"example" in lowered or len(set(key)) < 8:
        raise ValueError("DCAL_GROUP_HMAC_KEY appears to be a placeholder or weak key")
    return key


def opaque_id(key: bytes, namespace: str, value: str, *, prefix: str) -> str:
    validate_hmac_key(key)
    if not namespace or not value or not prefix:
        raise ValueError("opaque ID namespace, value, and prefix must be non-empty")
    digest = hmac.new(
        key,
        f"dcal:{namespace}:v1:{value}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    token = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")[:32]
    return f"{prefix}_{token}"


def task_ingestion_key(page_sha256: str) -> str:
    digest = hashlib.sha256(
        f"dcal:label-studio-task:v1:{page_sha256}".encode("ascii")
    ).hexdigest()
    return f"task_{digest[:32]}"
