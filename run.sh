#!/usr/bin/env bash
# One-command setup + start. Needs only Python 3.11+.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  echo "Python 3.11+ is required (found: $("$PY" --version 2>&1 || echo none))." >&2
  echo "Install it from https://www.python.org/downloads/ or set PYTHON=/path/to/python3.11" >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Creating virtual environment..."
  "$PY" -m venv .venv
fi

if [ ! -f .venv/.deps-installed ] || [ requirements.txt -nt .venv/.deps-installed ]; then
  echo "Installing dependencies..."
  if ! .venv/bin/python -m pip install -q -r requirements.txt; then
    echo "" >&2
    echo "pip install failed. On a corporate network with TLS inspection, point pip at your" >&2
    echo "organization's CA bundle:  PIP_CERT=/path/to/ca-bundle.pem ./run.sh" >&2
    exit 1
  fi
  touch .venv/.deps-installed
fi

if [ ! -f data/sandbox.db ]; then
  echo "Generating dataset..."
  .venv/bin/python -m datagen
fi

PORT="${PORT:-8000}"
case "$PORT" in *[!0-9]*|"") echo "PORT must be a number." >&2; exit 1 ;; esac
echo ""
echo "  T-Mobile Hackathon Sandbox (STUB DATA ONLY)"
echo "  API docs:  http://localhost:${PORT}/docs"
echo "  Health:    http://localhost:${PORT}/health"
echo ""
exec .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port "$PORT"
