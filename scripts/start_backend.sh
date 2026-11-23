#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
LOG_LEVEL="${LOG_LEVEL:-info}"
PID_FILE="${PID_FILE:-$ROOT_DIR/.lunaris-backend.pid}"
LOG_FILE="${LOG_FILE:-$ROOT_DIR/.lunaris-backend.log}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ROOT_DIR/.env"; set +a
  HOST="${HOST:-0.0.0.0}"
  PORT="${PORT:-8000}"
  LOG_LEVEL="${LOG_LEVEL:-info}"
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  elif [[ -x "$ROOT_DIR/.env/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.env/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: Python not found ($PYTHON_BIN)." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c "import fastapi, uvicorn, pydantic_settings, httpx" >/dev/null 2>&1; then
  echo "ERROR: Missing Python dependencies. Install with:" >&2
  echo "  $PYTHON_BIN -m pip install -r requirements.txt" >&2
  echo "  # or: $PYTHON_BIN -m pip install -r requirements-dev.txt" >&2
  exit 1
fi

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" >/dev/null 2>&1; then
    echo "ERROR: Backend already running (PID $OLD_PID, $PID_FILE)." >&2
    exit 1
  fi
  rm -f "$PID_FILE"
fi

echo "Starting LUNARIS backend on ${HOST}:${PORT}..."
nohup "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL" >"$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" >"$PID_FILE"

# Verify process started and health endpoint responds.
for _ in $(seq 1 30); do
  if ! kill -0 "$PID" >/dev/null 2>&1; then
    echo "ERROR: Backend process exited during startup. See $LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
  fi
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS "http://127.0.0.1:${PORT}${API_V1_PREFIX:-/api/v1}/health" >/dev/null 2>&1; then
      echo "OK: Backend started (PID $PID). Health: http://127.0.0.1:${PORT}${API_V1_PREFIX:-/api/v1}/health"
      echo "Docs: http://127.0.0.1:${PORT}/docs"
      echo "Logs: $LOG_FILE"
      exit 0
    fi
  fi
  sleep 1
done

if kill -0 "$PID" >/dev/null 2>&1; then
  echo "WARNING: Process is running (PID $PID) but health check did not pass yet. Check logs: $LOG_FILE" >&2
  exit 1
fi
echo "ERROR: Backend failed to start. See $LOG_FILE" >&2
rm -f "$PID_FILE"
exit 1
