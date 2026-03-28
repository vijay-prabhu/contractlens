#!/usr/bin/env bash

LOG_DIR="/tmp/contractlens-logs"
SERVICE="${1:-all}"

case "$SERVICE" in
  backend)
    tail -f "$LOG_DIR/backend.log"
    ;;
  frontend)
    tail -f "$LOG_DIR/frontend.log"
    ;;
  all)
    echo "Usage: ./dev-logs.sh [backend|frontend]"
    echo ""
    echo "Log files:"
    ls -la "$LOG_DIR/"*.log 2>/dev/null || echo "  No logs yet. Run ./dev-start.sh first."
    ;;
  *)
    echo "Unknown service: $SERVICE"
    echo "Usage: ./dev-logs.sh [backend|frontend]"
    ;;
esac
