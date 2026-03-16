#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost}"
ROL="${ROL:-CAJERO}"
PIN="${PIN:-}"
ENV_FILE="${ENV_FILE:-lite-edge/.env}"

load_pin_from_env_file() {
  local key="$1"
  local file="$2"
  if [[ ! -f "${file}" ]]; then
    return 1
  fi
  awk -F= -v k="${key}" '
    $1==k {
      v=substr($0, index($0, "=")+1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
      print v
      found=1
      exit
    }
    END { if (!found) exit 1 }
  ' "${file}"
}

usage() {
  cat <<'EOF'
Uso:
  ./scripts/smoke-local.sh

Variables opcionales:
  BASE_URL=https://localhost
  ROL=CAJERO|ADMIN
  PIN=1234
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "${PIN}" ]]; then
  if [[ "${ROL}" == "ADMIN" ]]; then
    PIN="${PIN_ADMIN:-}"
    [[ -z "${PIN}" ]] && PIN="$(load_pin_from_env_file "PIN_ADMIN" "${ENV_FILE}" || true)"
  else
    PIN="${PIN_CAJERO:-}"
    [[ -z "${PIN}" ]] && PIN="$(load_pin_from_env_file "PIN_CAJERO" "${ENV_FILE}" || true)"
  fi
fi

if [[ -z "${PIN}" ]]; then
  echo "Error: define PIN o PIN_CAJERO/PIN_ADMIN (env o ${ENV_FILE})" >&2
  exit 1
fi

curl_json() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local token="${4:-}"
  if [[ -n "${token}" ]]; then
    curl -ksS -X "${method}" "${BASE_URL}${path}" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${token}" \
      ${body:+-d "${body}"}
  else
    curl -ksS -X "${method}" "${BASE_URL}${path}" \
      -H "Content-Type: application/json" \
      ${body:+-d "${body}"}
  fi
}

echo "==> Status"
curl -ksS "${BASE_URL}/api/status" >/dev/null

echo "==> Unlock"
unlock_res="$(curl_json POST /api/auth/unlock "{\"pin\":\"${PIN}\",\"rol\":\"${ROL}\",\"usuario\":\"smoke\"}")"
token="$(printf '%s' "${unlock_res}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"

if [[ -z "${token}" ]]; then
  echo "Error: no se pudo obtener token de unlock" >&2
  exit 1
fi

echo "==> Jornada"
corte_res="$(curl -ksS -H "Authorization: Bearer ${token}" "${BASE_URL}/api/corte")"
if [[ "${corte_res}" == "null" ]]; then
  echo "Abriendo jornada para smoke..."
  curl_json POST /api/corte/abrir '{"caja_chica_inicial":100}' "${token}" >/dev/null
fi

echo "==> Venta"
if [[ -r /proc/sys/kernel/random/uuid ]]; then
  sale_id="$(cat /proc/sys/kernel/random/uuid)"
else
  sale_id="$(uuidgen)"
fi
venta_payload=$(cat <<EOF
{"client_sale_id":"${sale_id}","items":[{"producto_id":1,"nombre_snapshot":"Smoke Latte","precio_unitario":1,"cantidad":1,"modificadores_snapshot":[]}],"pago":{"metodo":"EFECTIVO","monto":1,"recibido":1},"total":1}
EOF
)
curl_json POST /api/comandas "${venta_payload}" "${token}" >/dev/null

echo "✅ Smoke local completado"
