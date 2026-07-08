#!/usr/bin/env bash
# Telegram multibot poller
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m bots.runner
