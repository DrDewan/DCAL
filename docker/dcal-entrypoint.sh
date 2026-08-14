#!/bin/sh
set -eu

mkdir -p /app/data/images /app/data/state
chown dcal:dcal /app/data/images /app/data/state

if [ "${1:-}" = "workbench" ]; then
  shift
  exec gosu dcal python -m dcal_workbench "$@"
fi

credential_source=${GOOGLE_APPLICATION_CREDENTIALS:-}
if [ -n "$credential_source" ]; then
  if [ ! -f "$credential_source" ]; then
    echo "Google Drive credential is missing or is not a file: $credential_source" >&2
    exit 2
  fi
  credential_copy=/tmp/dcal-google-drive-credentials.json
  install -o dcal -g dcal -m 0400 "$credential_source" "$credential_copy"
  export GOOGLE_APPLICATION_CREDENTIALS=$credential_copy
fi

exec gosu dcal python -m dcal_ingestion "$@"
