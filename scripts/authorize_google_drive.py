from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create an authorized-user credential for a dedicated DCAL Google account. "
            "Use a service account instead when DCAL has a Google Workspace Shared Drive."
        )
    )
    parser.add_argument("--client-secret", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("secrets/google-drive-credentials.json"),
    )
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "Install the OAuth extra first: python -m pip install -e '.[oauth]'",
            file=sys.stderr,
        )
        return 2
    if args.output.exists():
        print(
            f"Refusing to replace existing credentials: {args.output}",
            file=sys.stderr,
        )
        return 2

    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.client_secret), scopes=[DRIVE_SCOPE]
    )
    credentials = flow.run_local_server(
        host="localhost",
        port=args.port,
        authorization_prompt_message="Open this URL in your browser:\n{url}",
        success_message="DCAL Google Drive authorization completed. You can close this tab.",
        open_browser=True,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        args.output,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(credentials.to_json())
        handle.write("\n")
    print(f"Credentials written with owner-only permissions: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
