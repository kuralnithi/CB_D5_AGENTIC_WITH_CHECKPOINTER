#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  FinBot API — Starting up"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run Alembic database migrations before starting the server.
# This is safe to run on every startup; Alembic is idempotent.
echo "[startup] Running database migrations..."
python -m alembic upgrade head

echo "[startup] Migrations complete. Starting uvicorn on port 7860..."
exec uvicorn main:app --host 0.0.0.0 --port 7860
