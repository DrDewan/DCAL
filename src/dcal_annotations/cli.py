from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .taxonomy import DEFAULT_TAXONOMY_PATH, load_taxonomy
from .validation import ExportValidationError, normalize_export


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcal-annotations",
        description="Validate and normalize DCAL Label Studio exports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate-export", help="Validate an export without writing patient content."
    )
    validate.add_argument("input", type=Path)
    validate.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY_PATH)

    normalize = subparsers.add_parser(
        "normalize-export", help="Validate and write deterministic dcal.gold.v2 JSONL."
    )
    normalize.add_argument("input", type=Path)
    normalize.add_argument("--output", type=Path, required=True)
    normalize.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY_PATH)
    normalize.add_argument(
        "--force", action="store_true", help="Replace an existing output file."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        taxonomy = load_taxonomy(args.taxonomy)
        payload = _load_json(args.input)
        records = normalize_export(payload, taxonomy)
    except (OSError, json.JSONDecodeError, ValueError, ExportValidationError) as error:
        print(f"Validation failed:\n{error}", file=sys.stderr)
        return 2

    if args.command == "validate-export":
        print(f"Valid export: {len(records)} task(s).")
        return 0

    if args.output.exists() and not args.force:
        print(
            f"Refusing to replace existing output: {args.output}. Use --force explicitly.",
            file=sys.stderr,
        )
        return 3
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    print(f"Wrote {len(records)} normalized record(s) to {args.output}.")
    return 0
