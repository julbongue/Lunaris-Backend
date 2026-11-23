#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-quick}" # quick | named
PORT="${PORT:-8000}"
URL="${TUNNEL_URL:-http://localhost:${PORT}}"
CONFIG_FILE="${CLOUDFLARE_TUNNEL_CONFIG:-$ROOT_DIR/cloudflared/config.yml}"
PID_FILE="${TUNNEL_PID_FILE:-$ROOT_DIR/.lunaris-tunnel.pid}"
LOG_FILE="${TUNNEL_LOG_FILE:-$ROOT_DIR/.lunaris-tunnel.log}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ROOT_DIR/.env"; set +a
  PORT="${PORT:-8000}"
  URL="${TUNNEL_URL:-http://localhost:${PORT}}"
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "ERROR: cloudflared is not installed or not in PATH." >&2
  echo "Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
  exit 1
fi

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" >/dev/null 2>&1; then
    echo "ERROR: Tunnel already running (PID $OLD_PID)." >&2
    exit 1
  fi
  rm -f "$PID_FILE"
fi

case "$MODE" in
  quick)
    echo "Starting Cloudflare Quick Tunnel to ${URL} ..."
    nohup cloudflared tunnel --no-autoupdate --url "$URL" >"$LOG_FILE" 2>&1 &
    ;;
  named)
    if [[ ! -f "$CONFIG_FILE" ]]; then
      echo "ERROR: Named tunnel config not found: $CONFIG_FILE" >&2
      echo "Copy cloudflared/config.example.yml, fill your tunnel/name/credentials, and retry." >&2
      exit 1
    fi
    echo "Starting Cloudflare Named Tunnel using $CONFIG_FILE ..."
    nohup cloudflared tunnel --config "$CONFIG_FILE" run >"$LOG_FILE" 2>&1 &
    ;;
  *)
    echo "Usage: $0 [quick|named]" >&2
    exit 1
    ;;
esac

PID=$!
echo "$PID" >"$PID_FILE"
sleep 2
if ! kill -0 "$PID" >/dev/null 2>&1; then
  echo "ERROR: cloudflared exited during startup. See $LOG_FILE" >&2
  rm -f "$PID_FILE"
  exit 1
fi

echo "OK: cloudflared started (PID $PID). Logs: $LOG_FILE"
if [[ "$MODE" == "quick" ]]; then
  echo "Look in the log for the public trycloudflare.com URL (it may take a few seconds)."
fi
echo "IMPORTANT: Only the local API should be exposed (${URL}). Do not expose PostgreSQL/Redis."
