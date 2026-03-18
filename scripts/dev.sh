#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EDGE_DIR="${ROOT_DIR}/pos-edge"
PWA_DIR="${ROOT_DIR}/pos-pwa"

EDGE_PORT="${EDGE_PORT:-8000}"
PWA_PORT="${PWA_PORT:-5173}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Uso:
  ./scripts/dev.sh

Variables opcionales:
  EDGE_PORT  (default 8000)
  PWA_PORT   (default 5173)
EOF
  exit 0
fi

if [[ ! -x "${EDGE_DIR}/.venv/bin/python" ]]; then
  echo "Error: no existe virtualenv de Edge. Ejecuta ./scripts/bootstrap.sh primero." >&2
  exit 1
fi

if [[ ! -d "${PWA_DIR}/node_modules" ]]; then
  echo "Error: faltan dependencias de PWA. Ejecuta ./scripts/bootstrap.sh primero." >&2
  exit 1
fi

cleanup() {
  [[ -n "${EDGE_PID:-}" ]] && kill "${EDGE_PID}" >/dev/null 2>&1 || true
  [[ -n "${PWA_PID:-}" ]] && kill "${PWA_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "==> Iniciando Edge en :${EDGE_PORT}"
(
  cd "${EDGE_DIR}"
  source .venv/bin/activate
  uvicorn main:app --reload --host 0.0.0.0 --port "${EDGE_PORT}"
) &
EDGE_PID=$!

echo "==> Iniciando PWA en :${PWA_PORT}"
(
  cd "${PWA_DIR}"
  npm run dev -- --host --port "${PWA_PORT}"
) &
PWA_PID=$!

echo "==> Servicios levantados"
echo "    PWA:  http://localhost:${PWA_PORT}"
echo "    Edge: http://localhost:${EDGE_PORT}"

wait -n "${EDGE_PID}" "${PWA_PID}"
status=$?
echo "Uno de los procesos terminó (status=${status}). Apagando ambos."
exit "${status}"
