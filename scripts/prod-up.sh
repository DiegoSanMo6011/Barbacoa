#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/deploy/docker-compose.prod.yml"
SSL_DIR="${ROOT_DIR}/deploy/nginx/ssl"
EDGE_ENV="${ROOT_DIR}/lite-edge/.env"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: falta comando requerido: ${cmd}" >&2
    exit 1
  fi
}

require_cmd docker

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: docker compose plugin no disponible." >&2
  exit 1
fi

if [[ ! -f "${EDGE_ENV}" ]]; then
  echo "Error: falta ${EDGE_ENV}. Ejecuta ./scripts/bootstrap.sh y completa variables." >&2
  exit 1
fi

if [[ ! -f "${SSL_DIR}/pos-lite.crt" || ! -f "${SSL_DIR}/pos-lite.key" ]]; then
  cat <<'EOF' >&2
Error: faltan certificados TLS.
Genera primero:
  ./scripts/gen-local-cert.sh --ip <IP_LOCAL_POS>
EOF
  exit 1
fi

chmod 600 "${EDGE_ENV}" || true

docker compose -f "${COMPOSE_FILE}" up -d --build

local_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [[ -z "${local_ip}" ]]; then
  local_ip="$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {print $7; exit}')"
fi

echo "==> POS Lite en producción local"
echo "    https://pos-lite.local"
if [[ -n "${local_ip}" ]]; then
  echo "    https://${local_ip}"
fi
echo
echo "Tip: instala deploy/nginx/ssl/local-ca.crt en Android/iOS para evitar warnings TLS."
