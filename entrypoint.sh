#!/bin/sh
set -e

echo "Application des migrations Alembic..."
alembic upgrade head

echo "Démarrage de l'API (gunicorn + workers uvicorn)..."
exec gunicorn app.main:app \
  --workers "${GUNICORN_WORKERS:-4}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
