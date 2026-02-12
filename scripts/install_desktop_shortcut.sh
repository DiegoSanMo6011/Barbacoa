#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${HOME}/.local/share/applications"
DESKTOP_DIR="${HOME}/Desktop"
DESKTOP_DIR_ES="${HOME}/Escritorio"

mkdir -p "${TARGET_DIR}"
cat > "${TARGET_DIR}/autonoma-pos.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=AutoNoma POS
Comment=Sistema de ventas y control
Exec=${ROOT_DIR}/scripts/run_pos_local.sh
Path=${ROOT_DIR}
Icon=${ROOT_DIR}/app/assets/logo_autonoma.png
Terminal=false
Categories=Office;PointOfSale;
EOF

# Opcional: copiar al Escritorio si existe
if [[ -d "${DESKTOP_DIR}" ]]; then
  cp "${TARGET_DIR}/autonoma-pos.desktop" "${DESKTOP_DIR}/AutoNoma POS.desktop"
  chmod +x "${DESKTOP_DIR}/AutoNoma POS.desktop"
fi
if [[ -d "${DESKTOP_DIR_ES}" ]]; then
  cp "${TARGET_DIR}/autonoma-pos.desktop" "${DESKTOP_DIR_ES}/AutoNoma POS.desktop"
  chmod +x "${DESKTOP_DIR_ES}/AutoNoma POS.desktop"
fi

chmod +x "${TARGET_DIR}/autonoma-pos.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${TARGET_DIR}" >/dev/null 2>&1 || true
fi

if command -v gio >/dev/null 2>&1; then
  if [[ -f "${DESKTOP_DIR}/AutoNoma POS.desktop" ]]; then
    gio set "${DESKTOP_DIR}/AutoNoma POS.desktop" metadata::trusted true || true
  fi
  if [[ -f "${DESKTOP_DIR_ES}/AutoNoma POS.desktop" ]]; then
    gio set "${DESKTOP_DIR_ES}/AutoNoma POS.desktop" metadata::trusted true || true
  fi
fi

echo "Shortcut instalado en: ${TARGET_DIR}"
if [[ -d "${DESKTOP_DIR}" ]]; then
  echo "Shortcut en Escritorio: ${DESKTOP_DIR}/AutoNoma POS.desktop"
fi
if [[ -d "${DESKTOP_DIR_ES}" ]]; then
  echo "Shortcut en Escritorio: ${DESKTOP_DIR_ES}/AutoNoma POS.desktop"
fi
