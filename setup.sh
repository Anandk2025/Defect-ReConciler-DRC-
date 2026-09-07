#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo
echo "============================================"
echo " Defect ReConciler (DRC) - local setup"
echo " ZDR <-> Rally Sync"
echo "============================================"
echo

if [[ ! -f requirements.txt ]]; then
  echo "[ERROR] requirements.txt not found."
  echo "Run this script from inside the ZDR Rally Sync Up project folder."
  exit 1
fi

echo "[1/4] Looking for Python 3.9 or newer..."
PY_CMD=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >/dev/null 2>&1; then
      PY_CMD="$candidate"
      break
    fi
  fi
done

if [[ -z "$PY_CMD" ]]; then
  echo "[ERROR] Python 3.9 or newer was not found on PATH."
  echo "Install Python 3.9+ from https://www.python.org/downloads/ then run this again."
  exit 1
fi

"$PY_CMD" --version
echo

echo "[2/4] Creating virtual environment in .venv ..."
if [[ -x .venv/bin/python ]]; then
  echo "       .venv already exists - reusing it."
else
  "$PY_CMD" -m venv .venv
fi

VENV_PY=".venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "[ERROR] .venv exists but python was not found inside it."
  exit 1
fi

echo
echo "[3/4] Installing libraries from requirements.txt ..."
"$VENV_PY" -m pip install --upgrade pip || echo "[WARN] Could not upgrade pip. Continuing with the current version."
"$VENV_PY" -m pip install -r requirements.txt

echo
echo "[4/4] Environment file..."
if [[ -f .env ]]; then
  echo "       .env already exists - leaving it unchanged."
else
  cp .env.example .env
  echo "       Created .env from .env.example."
  echo "       Fill in Rally cookies and your Jira API token before running."
fi

echo
echo "============================================"
echo " Setup complete."
echo "============================================"
echo
echo "Next steps:"
echo "  1. Open .env and fill in:"
echo "       RALLY_ZSESSIONID, RALLY_JSESSIONID"
echo "       ZDR_JIRA_EMAIL, ZDR_JIRA_API_TOKEN"
echo "  2. Start the dashboard:"
echo "       .venv/bin/python -m src.server"
echo "     Then open http://127.0.0.1:5050"
echo
echo "Optional: Comments Sync Status needs the Claude CLI"
echo "installed and logged in (claude /login)."
echo
