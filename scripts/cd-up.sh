#!/usr/bin/env bash
# Host origin + named Cloudflare tunnel for the public demo.
# Secrets stay in gitignored .env (CLOUD_FARE_TOKEN).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

RUN_LOG_DIR="${RUN_LOG_DIR:-/tmp/hackspain-runs}"
BACKEND_PID_FILE="${CD_BACKEND_PID:-/tmp/hackspain-cd-backend.pid}"
FRONTEND_PID_FILE="${CD_FRONTEND_PID:-/tmp/hackspain-cd-frontend.pid}"
TUNNEL_PID_FILE="${CD_TUNNEL_PID:-/tmp/hackspain-cd-tunnel.pid}"
TUNNEL_LOG="${CD_TUNNEL_LOG:-/tmp/hackspain-cd-tunnel.log}"
BACKEND_LOG="${CD_BACKEND_LOG:-/tmp/hackspain-cd-backend.log}"
FRONTEND_LOG="${CD_FRONTEND_LOG:-/tmp/hackspain-cd-frontend.log}"

alive() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

if ! listening 8000; then
  mkdir -p "$RUN_LOG_DIR"
  NEO4J_ENABLED="${NEO4J_ENABLED:-false}" RUN_LOG_DIR="$RUN_LOG_DIR" PYTHONPATH=backend \
    backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    >"$BACKEND_LOG" 2>&1 &
  echo $! >"$BACKEND_PID_FILE"
  echo "backend: started"
else
  echo "backend: already running"
fi

if ! listening 3000; then
  (
    cd "$ROOT/frontend"
    unset VITE_API_BASE_URL
    export PATH="${HOME}/.bun/bin:${PATH}"
    # Tunnel ingress is http://localhost:3000, which resolves to [::1] on this Mac.
    bun run dev -- --host :: --port 3000
  ) >"$FRONTEND_LOG" 2>&1 &
  echo $! >"$FRONTEND_PID_FILE"
  echo "frontend: started"
else
  echo "frontend: already running"
fi

token="${CLOUD_FARE_TOKEN-}"
token="${token#\"}"
token="${token%\"}"
if [[ -z "$token" ]]; then
  echo "CLOUD_FARE_TOKEN missing in .env" >&2
  exit 1
fi
if alive "$TUNNEL_PID_FILE"; then
  echo "tunnel: already running"
else
  cloudflared tunnel run --protocol http2 --token "$token" >"$TUNNEL_LOG" 2>&1 &
  echo $! >"$TUNNEL_PID_FILE"
  echo "tunnel: started"
fi

for _ in $(seq 1 40); do
  if curl -sf -m 1 "http://127.0.0.1:8000/health" >/dev/null; then
    echo "backend: ready"
    exit 0
  fi
  sleep 0.25
done
echo "backend: did not become ready (see $BACKEND_LOG)" >&2
exit 1
