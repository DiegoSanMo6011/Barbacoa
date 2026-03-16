#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP_ARCHIVE="/tmp/pos_lite_config_${STAMP}.tar.gz"
DEST_BASENAME="pos_lite_config_${STAMP}.tar.gz"

usage() {
  cat <<'EOF'
Uso:
  ./scripts/backup-local-config.sh

Variables opcionales:
  OUT_DIR=/ruta/destino
  BACKUP_PASSPHRASE=clave-para-cifrado

Incluye:
  lite-edge/.env
  deploy/docker-compose.prod.yml
  deploy/nginx/conf.d
  deploy/nginx/nginx.conf
  deploy/nginx/ssl
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

mkdir -p "${OUT_DIR}"

entries=()
[[ -f "${ROOT_DIR}/lite-edge/.env" ]] && entries+=("lite-edge/.env")
[[ -f "${ROOT_DIR}/deploy/docker-compose.prod.yml" ]] && entries+=("deploy/docker-compose.prod.yml")
[[ -d "${ROOT_DIR}/deploy/nginx/conf.d" ]] && entries+=("deploy/nginx/conf.d")
[[ -f "${ROOT_DIR}/deploy/nginx/nginx.conf" ]] && entries+=("deploy/nginx/nginx.conf")
[[ -d "${ROOT_DIR}/deploy/nginx/ssl" ]] && entries+=("deploy/nginx/ssl")

if [[ "${#entries[@]}" -eq 0 ]]; then
  echo "Error: no hay archivos para respaldar." >&2
  exit 1
fi

(
  cd "${ROOT_DIR}"
  tar -czf "${TMP_ARCHIVE}" "${entries[@]}"
)

if [[ -n "${BACKUP_PASSPHRASE:-}" ]]; then
  out_file="${OUT_DIR}/${DEST_BASENAME}.enc"
  openssl enc -aes-256-cbc -pbkdf2 -salt \
    -in "${TMP_ARCHIVE}" \
    -out "${out_file}" \
    -pass "env:BACKUP_PASSPHRASE"
  sha256sum "${out_file}" > "${out_file}.sha256"
  rm -f "${TMP_ARCHIVE}"
  echo "Backup cifrado generado: ${out_file}"
  echo "Checksum: ${out_file}.sha256"
else
  out_file="${OUT_DIR}/${DEST_BASENAME}"
  mv "${TMP_ARCHIVE}" "${out_file}"
  sha256sum "${out_file}" > "${out_file}.sha256"
  echo "Backup generado: ${out_file}"
  echo "Checksum: ${out_file}.sha256"
fi
