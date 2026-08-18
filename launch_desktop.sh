#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="http://127.0.0.1:8765"

if ! ss -ltn "sport = :8765" | grep -q LISTEN; then
  "${APP_DIR}/start.sh" &
  SERVER_PID=$!
  sleep 1
else
  SERVER_PID=""
fi

xdg-open "${URL}"

if [ -n "${SERVER_PID}" ]; then
  wait "${SERVER_PID}"
fi
