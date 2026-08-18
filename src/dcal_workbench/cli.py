from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from .server import create_server
from .store import WorkbenchStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcal-workbench",
        description="Private DCAL page ingestion and upload service.",
    )
    parser.add_argument("--host", default=os.environ.get("DCAL_WORKBENCH_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("DCAL_WORKBENCH_PORT", "8090"))
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("DCAL_WORKBENCH_DATABASE", "data/workbench.sqlite3")),
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path(os.environ.get("DCAL_PAGE_CACHE_ROOT", "data/images")),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("DCAL_WORKBENCH_INGEST_TOKEN", "").strip()
    if not token or len(token) < 24 or token.startswith("replace-"):
        print(
            "DCAL_WORKBENCH_INGEST_TOKEN must be a non-placeholder secret of at least 24 characters",
            file=sys.stderr,
        )
        return 2
    if not 1 <= args.port <= 65535:
        print("port must be between 1 and 65535", file=sys.stderr)
        return 2
    store = WorkbenchStore(args.database, args.cache_root)
    server = create_server(args.host, args.port, store, token)
    print(f"DCAL ingestion service listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0

