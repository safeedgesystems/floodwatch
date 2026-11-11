#!/usr/bin/env bash
# One-command start for Linux/macOS: creates a venv, installs deps, runs the app.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
cd backend
echo "FloodWatch running at http://localhost:${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
