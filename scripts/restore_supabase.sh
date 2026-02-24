#!/usr/bin/env bash
set -euo pipefail

# Requires:
#   SUPABASE_DB_URL=postgresql://...
# Usage:
#   ./scripts/restore_supabase.sh backups/db/supabase_xxx.dump

if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
  echo "ERROR: SUPABASE_DB_URL is required"
  exit 1
fi

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <dump_file>"
  exit 1
fi

DUMP_FILE="$1"
if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "ERROR: dump file not found: ${DUMP_FILE}"
  exit 1
fi

pg_restore --clean --if-exists --no-owner --no-privileges --dbname="${SUPABASE_DB_URL}" "${DUMP_FILE}"

echo "Restore completed from: ${DUMP_FILE}"
