#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EDGE_DIR="${ROOT_DIR}/pos-edge"
PWA_DIR="${ROOT_DIR}/pos-pwa"

WITH_DB=0
WITH_SEED=0

usage() {
  cat <<'EOF'
Uso:
  ./scripts/bootstrap.sh [--with-db] [--with-seed]

Opciones:
  --with-db    Ejecuta migraciones SQL contra DATABASE_URL
  --with-seed  Ejecuta seed demo (requiere --with-db y TENANT_ID)
  -h, --help   Muestra esta ayuda

Variables esperadas:
  DATABASE_URL  (requerida si usas --with-db)
  TENANT_ID     (requerida si usas --with-seed)
EOF
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: falta comando requerido: $cmd" >&2
    exit 1
  fi
}

warn_if_placeholder_env() {
  local edge_env="${EDGE_DIR}/.env"
  [[ -f "${edge_env}" ]] || return 0
  if grep -Eq "tu-proyecto\.supabase\.co|tu-service-role-key|uuid-del-tenant-aqui" "${edge_env}"; then
    cat <<'EOF'
⚠️  Detecté placeholders en pos-edge/.env.
    Reemplaza SUPABASE_URL, SUPABASE_SERVICE_KEY y TENANT_ID con valores reales.
EOF
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-db)
      WITH_DB=1
      shift
      ;;
    --with-seed)
      WITH_SEED=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argumento no reconocido: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$WITH_SEED" -eq 1 && "$WITH_DB" -ne 1 ]]; then
  echo "Error: --with-seed requiere --with-db" >&2
  exit 1
fi

require_cmd python3
require_cmd npm

echo "==> Preparando Edge (Python venv + dependencias)"
if [[ ! -d "${EDGE_DIR}/.venv" ]]; then
  python3 -m venv "${EDGE_DIR}/.venv"
fi
"${EDGE_DIR}/.venv/bin/pip" install --upgrade pip >/dev/null
"${EDGE_DIR}/.venv/bin/pip" install -r "${EDGE_DIR}/requirements.txt"

if [[ ! -f "${EDGE_DIR}/.env" ]]; then
  cp "${EDGE_DIR}/.env.example" "${EDGE_DIR}/.env"
  echo "==> Creado ${EDGE_DIR}/.env (edita valores antes de correr Edge)"
fi
warn_if_placeholder_env

echo "==> Preparando PWA (npm install)"
npm --prefix "${PWA_DIR}" install

if [[ ! -f "${PWA_DIR}/.env" ]]; then
  cp "${PWA_DIR}/.env.example" "${PWA_DIR}/.env"
  echo "==> Creado ${PWA_DIR}/.env"
fi

if [[ "$WITH_DB" -eq 1 ]]; then
  if ! command -v psql >/dev/null 2>&1; then
    cat <<'EOF' >&2
Error: falta comando requerido: psql
Instala cliente PostgreSQL o ejecuta los SQL manualmente en Supabase SQL Editor:
  sql/01_schema_lite.sql
  sql/02_rls_policies.sql
  sql/03_rpcs.sql
  sql/04_go_live_hardening.sql
  sql/05_jornada_rpcs.sql
  sql/seed_demo_cafe.sql (opcional)
EOF
    exit 1
  fi
  : "${DATABASE_URL:?Error: define DATABASE_URL para ejecutar migraciones}"

  echo "==> Ejecutando migraciones SQL"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "${ROOT_DIR}/sql/01_schema_lite.sql"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "${ROOT_DIR}/sql/02_rls_policies.sql"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "${ROOT_DIR}/sql/03_rpcs.sql"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "${ROOT_DIR}/sql/04_go_live_hardening.sql"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "${ROOT_DIR}/sql/05_jornada_rpcs.sql"

  if [[ "$WITH_SEED" -eq 1 ]]; then
    : "${TENANT_ID:?Error: define TENANT_ID para ejecutar seed}"
    echo "==> Ejecutando seed demo para tenant ${TENANT_ID}"
    tmp_seed="$(mktemp)"
    trap 'rm -f "${tmp_seed}"' EXIT
    sed "s/TU-TENANT-ID-AQUI/${TENANT_ID}/g" "${ROOT_DIR}/sql/seed_demo_cafe.sql" > "${tmp_seed}"
    psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "${tmp_seed}"
  fi
fi

cat <<'EOF'
==> Bootstrap completado

Siguiente paso:
  ./scripts/dev.sh
EOF
