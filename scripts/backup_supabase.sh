#!/usr/bin/env bash
set -euo pipefail

# Requires:
#   SUPABASE_DB_URL=postgresql://...
# Optional:
#   BACKUP_DIR=backups/db

if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
  echo "ERROR: SUPABASE_DB_URL is required"
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-backups/db}"
mkdir -p "${BACKUP_DIR}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/supabase_${STAMP}.dump"

pg_dump --format=custom --file="${OUT}" "${SUPABASE_DB_URL}"

echo "Backup created: ${OUT}"
