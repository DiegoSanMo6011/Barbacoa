#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost}"
WEB_PATH="${WEB_PATH:-/}"
API_PATH="${API_PATH:-/api/status}"
MAX_LATENCY_MS="${MAX_LATENCY_MS:-2500}"
STATE_FILE="${STATE_FILE:-/tmp/pos_lite_health_state}"

usage() {
  cat <<'EOF'
Uso:
  ./scripts/monitor-health.sh

Variables opcionales:
  BASE_URL=https://localhost
  WEB_PATH=/
  API_PATH=/api/status
  MAX_LATENCY_MS=2500
  STATE_FILE=/tmp/pos_lite_health_state

Alertas opcionales:
  ALERT_TELEGRAM_BOT_TOKEN=...
  ALERT_TELEGRAM_CHAT_ID=...
  ALERT_EMAIL=ops@mi-dominio.com
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

notify() {
  local message="$1"

  if [[ -n "${ALERT_TELEGRAM_BOT_TOKEN:-}" && -n "${ALERT_TELEGRAM_CHAT_ID:-}" ]]; then
    curl -sS --max-time 10 \
      -X POST "https://api.telegram.org/bot${ALERT_TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${ALERT_TELEGRAM_CHAT_ID}" \
      -d "text=${message}" >/dev/null || true
  fi

  if [[ -n "${ALERT_EMAIL:-}" ]] && command -v mail >/dev/null 2>&1; then
    printf '%s\n' "${message}" | mail -s "POS Lite health alert" "${ALERT_EMAIL}" || true
  fi
}

check_endpoint() {
  local url="$1"
  local started_at finished_at latency

  started_at="$(date +%s%3N)"
  if ! curl -kfsS --max-time 8 "${url}" >/dev/null; then
    echo "DOWN|999999"
    return
  fi
  finished_at="$(date +%s%3N)"
  latency=$((finished_at - started_at))
  echo "UP|${latency}"
}

web_result="$(check_endpoint "${BASE_URL}${WEB_PATH}")"
api_result="$(check_endpoint "${BASE_URL}${API_PATH}")"

web_status="${web_result%%|*}"
web_latency="${web_result##*|}"
api_status="${api_result%%|*}"
api_latency="${api_result##*|}"

overall="OK"
if [[ "${web_status}" != "UP" || "${api_status}" != "UP" ]]; then
  overall="DOWN"
elif (( web_latency > MAX_LATENCY_MS || api_latency > MAX_LATENCY_MS )); then
  overall="SLOW"
fi

previous="UNKNOWN"
if [[ -f "${STATE_FILE}" ]]; then
  previous="$(cat "${STATE_FILE}" 2>/dev/null || echo UNKNOWN)"
fi
echo "${overall}" > "${STATE_FILE}"

timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
message="[$timestamp] POS Lite health=${overall} web=${web_status}/${web_latency}ms api=${api_status}/${api_latency}ms base=${BASE_URL}"

if [[ "${overall}" != "${previous}" ]]; then
  notify "${message}"
fi

echo "${message}"
if [[ "${overall}" == "OK" ]]; then
  exit 0
fi
exit 1
