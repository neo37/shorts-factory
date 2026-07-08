#!/usr/bin/env bash
# Flask web + admin + external API
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 --timeout 120 wsgi:app
