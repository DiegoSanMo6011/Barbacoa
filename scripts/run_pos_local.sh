#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${ROOT_DIR}/pos_launcher.log"
VENV_PY="${ROOT_DIR}/.venv/bin/python"

echo "=== POS launch $(date) ===" >> "${LOG}"
echo "USER=$(whoami) DISPLAY=${DISPLAY:-} PWD=$(pwd)" >> "${LOG}"

cd "${ROOT_DIR}" || exit 1

if [ -x "${VENV_PY}" ]; then
  "${VENV_PY}" "${ROOT_DIR}/app/main.py" >> "${LOG}" 2>&1
else
  python3 "${ROOT_DIR}/app/main.py" >> "${LOG}" 2>&1
fi
