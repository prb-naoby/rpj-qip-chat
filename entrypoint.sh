#!/bin/bash
set -e

MODE=${MODE:-backend}

case "$MODE" in
  frontend)
    echo "Starting QIP Frontend..."
    cd /app/frontend
    export HOSTNAME="0.0.0.0"
    export PORT="3000"
    exec node server.js
    ;;
  backend)
    echo "Starting QIP Backend..."
    cd /app
    exec uvicorn api.main:app --host 0.0.0.0 --port 1234 --timeout-keep-alive 300
    ;;
  *)
    echo "Unknown MODE: $MODE. Use 'frontend' or 'backend'"
    exit 1
    ;;
esac
