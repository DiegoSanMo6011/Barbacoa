#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/deploy/docker-compose.prod.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker no está instalado." >&2
  exit 1
fi

if [[ "${1:-}" == "--volumes" ]]; then
  docker compose -f "${COMPOSE_FILE}" down --remove-orphans --volumes
else
  docker compose -f "${COMPOSE_FILE}" down --remove-orphans
fi
