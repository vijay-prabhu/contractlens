#!/usr/bin/env bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

LOG_DIR="/tmp/contractlens-logs"
PID_FILE="$LOG_DIR/pids"

ok()  { echo -e "${GREEN}[✓]${NC} $1"; }

# ─── Kill app processes from PID file ────────────────────────────────
if [ -f "$PID_FILE" ]; then
  while read -r pid; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
fi

# ─── Kill by process pattern (fallback) ─────────────────────────────
pkill -f "uvicorn app.main:app.*--port 8200" 2>/dev/null || true
pkill -f "next dev.*-p 3200" 2>/dev/null || true

# ─── Kill by port (final fallback) ──────────────────────────────────
lsof -ti:8200 | xargs kill -9 2>/dev/null || true
lsof -ti:3200 | xargs kill -9 2>/dev/null || true

ok "All services stopped"
echo "Logs preserved at: $LOG_DIR/"
echo ""
