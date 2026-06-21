#!/bin/sh
# Startup: (re)build reference seed from the template and load it (both idempotent),
# then launch the app. Tables, migrations and the uploads dir are created on import.
set -e

python scripts/extract_seed.py || echo "seed extract skipped"
python -m app.seed || echo "seed load skipped"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
