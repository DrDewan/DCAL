from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
from pathlib import Path
from typing import Sequence

from .config import DriveRuntimeConfig, SyncRuntimeConfig
from .drive import GoogleDriveGateway
from .drive import LAYOUT_FOLDERS
from .label_studio import LabelStudioClient
from .ledger import IngestionLedger
from .recovery import audit_drive, restore_page_cache
from .render import render_local_file
from .service import IngestionService, IngestionSettings


def _print_event(event: str, payload: dict[str, object]) -> None:
    print(json.dumps({"event": event, **payload}, sort_keys=True), flush=True)


def _drive(config: DriveRuntimeConfig) -> GoogleDriveGateway:
    return GoogleDriveGateway.from_credentials(
        config.credentials_path, delegated_subject=config.delegated_subject
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcal-ingest",
        description="Checksum-first Google Drive ingestion for DCAL.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser(
        "bootstrap-drive", help="Create or adopt the versioned DCAL Drive folders."
    )
    bootstrap.add_argument("--root-folder-id")

    subparsers.add_parser("doctor", help="Verify credentials and the Drive layout.")
    subparsers.add_parser("sync-once", help="Ingest all valid inbox sources once.")

    watch = subparsers.add_parser("watch", help="Continuously poll the Drive inbox.")
    watch.add_argument("--interval", type=int, default=60)

    subparsers.add_parser(
        "audit-drive", help="Download and verify every archived checksum and lock."
    )
    subparsers.add_parser(
        "restore-cache", help="Rebuild the derived Label Studio page cache from Drive."
    )

    render = subparsers.add_parser(
        "render-local", help="Render a local synthetic source with the production profile."
    )
    render.add_argument("input", type=Path)
    render.add_argument("--mime-type")
    render.add_argument("--output-dir", type=Path, required=True)
    return parser


def _sync_once(config: SyncRuntimeConfig) -> tuple[dict[str, int], bool]:
    drive = _drive(config.drive)
    layout = drive.resolve_layout(config.drive.root_folder_id)
    label_studio = LabelStudioClient(
        config.label_studio_url,
        config.label_studio_token,
        config.label_studio_project_id,
    )
    with IngestionLedger(config.drive.ledger_path) as ledger:
        service = IngestionService(
            drive=drive,
            label_studio=label_studio,
            ledger=ledger,
            layout=layout,
            settings=IngestionSettings(
                hmac_key=config.hmac_key,
                cache_root=config.drive.cache_root,
            ),
        )
        summary = service.sync_once()
    return summary.as_dict(), summary.successful


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "render-local":
            mime_type = args.mime_type or mimetypes.guess_type(args.input.name)[0]
            if not mime_type:
                raise ValueError("unable to determine MIME type; pass --mime-type")
            pages = list(render_local_file(args.input, mime_type))
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for page in pages:
                destination = args.output_dir / f"page-{page.page_index:04d}-{page.sha256}.png"
                destination.write_bytes(page.content)
            _print_event("render_complete", {"pages": len(pages)})
            return 0

        drive_config = DriveRuntimeConfig.from_env(require_root=False)
        if args.command == "bootstrap-drive":
            root = (args.root_folder_id or drive_config.root_folder_id).strip()
            if not root:
                raise ValueError(
                    "pass --root-folder-id or set DCAL_DRIVE_ROOT_FOLDER_ID"
                )
            layout = _drive(drive_config).bootstrap_layout(root)
            _print_event(
                "drive_bootstrapped",
                {
                    "schema_version": layout.as_dict()["schema_version"],
                    "folder_roles": sorted(LAYOUT_FOLDERS),
                },
            )
            return 0

        if not drive_config.root_folder_id:
            raise ValueError("DCAL_DRIVE_ROOT_FOLDER_ID is required")
        if args.command in {"doctor", "audit-drive", "restore-cache"}:
            drive = _drive(drive_config)
            layout = drive.resolve_layout(drive_config.root_folder_id)
        if args.command == "doctor":
            _print_event(
                "doctor_ok",
                {"schema_version": layout.as_dict()["schema_version"]},
            )
            return 0
        if args.command == "audit-drive":
            summary = audit_drive(drive, layout)
            _print_event("drive_audit", summary.as_dict())
            return 0 if summary.successful else 2
        if args.command == "restore-cache":
            summary = restore_page_cache(drive, layout, drive_config.cache_root)
            _print_event("cache_restore", summary.as_dict())
            return 0 if summary.successful else 2

        sync_config = SyncRuntimeConfig.from_env()
        if args.command == "sync-once":
            payload, successful = _sync_once(sync_config)
            _print_event("sync_complete", payload)
            return 0 if successful else 2
        if args.command == "watch":
            if args.interval < 15:
                raise ValueError("watch interval must be at least 15 seconds")
            while True:
                payload, successful = _sync_once(sync_config)
                _print_event("sync_complete", payload)
                if not successful:
                    _print_event("sync_retry_scheduled", {"seconds": args.interval})
                time.sleep(args.interval)
    except KeyboardInterrupt:
        _print_event("stopped", {})
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print(f"DCAL ingestion failed: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(
            f"DCAL ingestion failed with an external {type(error).__name__}; "
            "no source identifiers were logged",
            file=sys.stderr,
        )
        return 2
    return 0
