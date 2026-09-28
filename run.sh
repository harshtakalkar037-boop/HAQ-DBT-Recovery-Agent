#!/usr/bin/env bash
# HAQ — DBT Payment Recovery Agent · start the full application
cd "$(dirname "$0")"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
