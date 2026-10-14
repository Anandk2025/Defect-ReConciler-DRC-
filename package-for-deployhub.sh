#!/usr/bin/env bash
# Build a DeployHub upload zip that never includes .env or other secrets.
set -euo pipefail
cd "$(dirname "$0")"

OUT="${1:-drc-deployhub.zip}"
rm -f "$OUT"

zip -r "$OUT" . \
  -x '.env' \
  -x '.venv/*' \
  -x '.git/*' \
  -x '.cursor/*' \
  -x '.claude/*' \
  -x '*__pycache__*' \
  -x '*.pyc' \
  -x '.DS_Store' \
  -x 'reports/*' \
  -x '*.zip' \
  -x 'package-for-deployhub.sh'

echo
echo "Created $OUT"
echo "Do not zip the project folder by hand — that includes .env and DeployHub will block it."
echo "Set secrets in DeployHub → Environment variables (not in the zip)."
