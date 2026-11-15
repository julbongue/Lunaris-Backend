#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-}"
PORT="${PORT:-8000}"
API_V1_PREFIX="${API_V1_PREFIX:-/api/v1}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ROOT_DIR/.env"; set +a
  PORT="${PORT:-8000}"
  API_V1_PREFIX="${API_V1_PREFIX:-/api/v1}"
fi

if [[ -z "$BASE_URL" ]]; then
  BASE_URL="http://127.0.0.1:${PORT}"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required for health checks." >&2
  exit 1
fi

echo "Checking LUNARIS API at ${BASE_URL}"
echo

echo "[1/3] Root: ${BASE_URL}/"
ROOT_RESP="$(curl -fsS "${BASE_URL}/")" || { echo "FAIL: root endpoint"; exit 1; }
echo "$ROOT_RESP"

echo
echo "[2/3] Health: ${BASE_URL}${API_V1_PREFIX}/health"
HEALTH_RESP="$(curl -fsS "${BASE_URL}${API_V1_PREFIX}/health")" || { echo "FAIL: health endpoint"; exit 1; }
echo "$HEALTH_RESP"

echo
echo "[3/3] Capabilities: ${BASE_URL}${API_V1_PREFIX}/capabilities"
CAP_RESP="$(curl -fsS "${BASE_URL}${API_V1_PREFIX}/capabilities")" || { echo "FAIL: capabilities endpoint"; exit 1; }
echo "$CAP_RESP"

echo
echo "OK: API is reachable and healthy."
