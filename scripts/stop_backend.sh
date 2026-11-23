#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID_FILE="${BACKEND_PID_FILE:-$ROOT_DIR/.lunaris-backend.pid}"
TUNNEL_PID_FILE="${TUNNEL_PID_FILE:-$ROOT_DIR/.lunaris-tunnel.pid}"

stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  if [[ ! -f "$pid_file" ]]; then
    echo "$name: no PID file ($pid_file)."
    return 0
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    rm -f "$pid_file"
    echo "$name: empty PID file removed."
    return 0
  fi
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    rm -f "$pid_file"
    echo "$name: process $pid not running; PID file removed."
    return 0
  fi
  echo "Stopping $name (PID $pid)..."
  kill "$pid" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      rm -f "$pid_file"
      echo "$name: stopped."
      return 0
    fi
    sleep 0.5
  done
  echo "$name: forcing stop (PID $pid)..."
  kill -9 "$pid" >/dev/null 2>&1 || true
  rm -f "$pid_file"
  echo "$name: forced stop."
}

case "${1:-all}" in
  backend) stop_pid_file "backend" "$BACKEND_PID_FILE" ;;
  tunnel) stop_pid_file "tunnel" "$TUNNEL_PID_FILE" ;;
  all)
    stop_pid_file "tunnel" "$TUNNEL_PID_FILE"
    stop_pid_file "backend" "$BACKEND_PID_FILE"
    ;;
  *)
    echo "Usage: $0 [all|backend|tunnel]" >&2
    exit 1
    ;;
esac
