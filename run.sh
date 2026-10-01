#!/usr/bin/env bash
# Start the Hack4Seniors backend (FastAPI) and frontend (Expo) for development.
#
#   ./run.sh            backend + demo data + Expo
#   ./run.sh backend    backend + demo data only
#   ./run.sh frontend   Expo only (expects the backend to be running already)
#
# Env overrides: API_PORT (default 8000), API_HOST (IP the phone uses to reach the API).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
MODE="${1:-all}"
API_PORT="${API_PORT:-8000}"

log() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# IP reachable from a phone on the same Wi-Fi (Expo Go); falls back to localhost.
lan_ip() {
  ipconfig getifaddr en0 2>/dev/null \
    || ipconfig getifaddr en1 2>/dev/null \
    || hostname -I 2>/dev/null | awk '{print $1}' \
    || true
}
API_HOST="${API_HOST:-$(lan_ip)}"
API_HOST="${API_HOST:-localhost}"
API_URL="http://$API_HOST:$API_PORT"

setup_backend() {
  command -v python3 >/dev/null || die "python3 is required"
  cd "$BACKEND"
  if [ ! -d .venv ]; then
    log "Creating Python virtualenv"
    python3 -m venv .venv
  fi
  # Reinstall only when requirements.txt changes.
  if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
    log "Installing backend dependencies"
    .venv/bin/pip install -q --upgrade pip
    .venv/bin/pip install -q -r requirements.txt
    touch .venv/.installed
  fi
  if [ ! -f .env ]; then
    log "Creating backend/.env (admin: admin@demo.cl / admin1234)"
    cat > .env <<EOF
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
ADMIN_EMAIL=admin@demo.cl
ADMIN_PASSWORD=admin1234
STORAGE=flatfile
STORAGE_PATH=$BACKEND/data
EOF
  fi
}

BACKEND_PID=""
cleanup() {
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Stopping backend"
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}

start_backend() {
  if curl -sf "http://localhost:$API_PORT/health" >/dev/null; then
    die "something is already listening on port $API_PORT (stop it or set API_PORT)"
  fi
  log "Starting backend on $API_URL (docs: $API_URL/docs)"
  cd "$BACKEND/src"
  ../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port "$API_PORT" --reload &
  BACKEND_PID=$!
  trap cleanup EXIT INT TERM

  for _ in $(seq 1 60); do
    curl -sf "http://localhost:$API_PORT/health" >/dev/null && break
    kill -0 "$BACKEND_PID" 2>/dev/null || die "backend failed to start"
    sleep 0.5
  done
  curl -sf "http://localhost:$API_PORT/health" >/dev/null || die "backend did not become healthy"

  log "Loading demo data"
  "$BACKEND/.venv/bin/python" "$BACKEND/scripts/seed.py" "http://localhost:$API_PORT"
}

start_frontend() {
  # Prefer Node/npm; fall back to Bun if that's all that is installed.
  local install exec
  if command -v npm >/dev/null; then
    install="npm install"; exec="npx"
  elif command -v bun >/dev/null || [ -x "$HOME/.bun/bin/bun" ]; then
    local bun; bun="$(command -v bun || echo "$HOME/.bun/bin/bun")"
    install="$bun install"; exec="$bun x --bun"
  else
    die "Node.js 20+ (or Bun) is required to run the frontend"
  fi
  cd "$FRONTEND"
  if [ ! -d node_modules ] || [ package.json -nt node_modules ]; then
    log "Installing frontend dependencies"
    $install
    $exec expo install --fix
    touch node_modules
  fi
  log "Starting Expo (API: $API_URL) — demo login: rosa@demo.cl / rosa1234"
  EXPO_PUBLIC_API_URL="$API_URL" $exec expo start
}

case "$MODE" in
  all)
    setup_backend
    start_backend
    start_frontend
    ;;
  backend)
    setup_backend
    start_backend
    log "Backend running — press Ctrl+C to stop"
    wait "$BACKEND_PID"
    ;;
  frontend)
    start_frontend
    ;;
  *)
    die "usage: $0 [all|backend|frontend]"
    ;;
esac
