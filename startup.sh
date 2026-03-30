#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  FinBot API — Starting up"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run Alembic database migrations before starting the server.
# This is safe to run on every startup; Alembic is idempotent.
echo "[startup] Running database migrations..."
# [FIX] Force-sync the database to the baseline revision to resolve missing 'c9d0e1f2a3b4' errors.
python -m alembic stamp --purge 001_langgraph_setup
python -m alembic upgrade head

echo "[startup] Migrations complete. Starting uvicorn on port 7860..."
exec uvicorn main:app --host 0.0.0.0 --port 7860
