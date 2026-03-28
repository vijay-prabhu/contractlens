#!/usr/bin/env bash
set -e

LOG_DIR="/tmp/contractlens-logs"
mkdir -p "$LOG_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$LOG_DIR/pids"

log() { echo -e "${BLUE}[contractlens]${NC} $1"; }
ok()  { echo -e "${GREEN}[✓]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

# Clean up old PIDs
> "$PID_FILE"

# ─── Kill any existing processes on our ports ───────────────────────
lsof -ti:8200 | xargs kill -9 2>/dev/null || true
lsof -ti:3200 | xargs kill -9 2>/dev/null || true
sleep 1

# ─── 1. Backend (FastAPI on port 8200) ──────────────────────────────
log "Starting backend..."
cd "$PROJECT_ROOT/backend"
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8200 > "$LOG_DIR/backend.log" 2>&1 &
echo "$!" >> "$PID_FILE"

for i in $(seq 1 15); do
  if curl -sf http://localhost:8200/health > /dev/null 2>&1; then
    ok "Backend ready → http://localhost:8200"
    break
  fi
  sleep 1
done

if ! curl -sf http://localhost:8200/health > /dev/null 2>&1; then
  err "Backend failed to start. Check $LOG_DIR/backend.log"
  exit 1
fi

# ─── 2. Frontend (Next.js on port 3200) ─────────────────────────────
log "Starting frontend..."
cd "$PROJECT_ROOT/frontend"
npm run dev -- -p 3200 > "$LOG_DIR/frontend.log" 2>&1 &
echo "$!" >> "$PID_FILE"

for i in $(seq 1 15); do
  if curl -sf http://localhost:3200 > /dev/null 2>&1; then
    ok "Frontend ready → http://localhost:3200"
    break
  fi
  sleep 1
done

if ! curl -sf http://localhost:3200 > /dev/null 2>&1; then
  warn "Frontend may still be starting. Check $LOG_DIR/frontend.log"
fi

# ─── Summary ────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} ContractLens — All services running${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Frontend      → http://localhost:3200"
echo "  Backend API   → http://localhost:8200"
echo "  API Docs      → http://localhost:8200/docs"
echo ""
echo "  Logs:  $LOG_DIR/"
echo "    backend.log, frontend.log"
echo ""
echo -e "  Stop all:  ${YELLOW}./dev-stop.sh${NC}"
echo -e "  View logs: ${YELLOW}./dev-logs.sh [backend|frontend]${NC}"
echo ""
