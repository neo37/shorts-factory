#!/usr/bin/env bash
# Celery worker — MUST stay single-threaded (concurrency=1) so ffmpeg/render never overload CPU.
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/celery -A app.celery_app.celery worker \
  --loglevel=INFO --concurrency=1 -Q videobot -n videobot@%h
