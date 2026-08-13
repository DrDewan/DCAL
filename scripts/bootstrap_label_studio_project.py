#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = (
    REPOSITORY_ROOT / "config" / "label-studio" / "bmch-page-annotation.v1.xml"
)
DEFAULT_TITLE = "BMCH Page Classification and OCR v1"


def _request(url: str, token: str, *, method: str = "GET", body: Any = None) -> Any:
    data = None
    headers = {"Authorization": f"Token {token}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _project_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return [item for item in payload["results"] if isinstance(item, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the versioned DCAL annotation project in Label Studio."
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("LABEL_STUDIO_HOST", "http://localhost:8080"),
        help="Label Studio base URL.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("LABEL_STUDIO_API_TOKEN"),
        help="Label Studio API token; defaults to LABEL_STUDIO_API_TOKEN.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the request body without calling the API."
    )
    args = parser.parse_args()

    try:
        label_config = args.config.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Unable to read annotation config: {error}", file=sys.stderr)
        return 2

    payload = {
        "title": args.title,
        "description": (
            "DCAL v1 single-page BMCH physical classification and region-level exact "
            "transcription. Machine predictions are suggestions, never ground truth."
        ),
        "label_config": label_config,
        "maximum_annotations": 1,
        "enable_empty_annotation": False,
        "evaluate_predictions_automatically": True,
        "show_collab_predictions": True,
        "show_instruction": True,
        "show_skip_button": True,
        "sampling": "Sequential sampling",
        "expert_instruction": (
            "Classify the physical page, record quality defects, and annotate every "
            "meaningful variable region. Transcribe only visible content. Use unknown "
            "and illegible instead of guessing."
        ),
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if not args.token:
        print(
            "Set LABEL_STUDIO_API_TOKEN or pass --token. The token is never written to disk.",
            file=sys.stderr,
        )
        return 2

    base_url = args.url.rstrip("/")
    try:
        existing_payload = _request(
            f"{base_url}/api/projects/?page_size=100", args.token
        )
        existing = next(
            (
                project
                for project in _project_list(existing_payload)
                if project.get("title") == args.title
            ),
            None,
        )
        if existing is not None:
            print(
                f"Project already exists: id={existing.get('id')} "
                f"{base_url}/projects/{existing.get('id')}/"
            )
            return 0

        created = _request(
            f"{base_url}/api/projects/", args.token, method="POST", body=payload
        )
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print(f"Label Studio returned HTTP {error.code}: {detail}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Unable to reach Label Studio: {error}", file=sys.stderr)
        return 1

    print(f"Created project: id={created.get('id')} {base_url}/projects/{created.get('id')}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
