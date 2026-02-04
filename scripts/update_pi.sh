
#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

ENV_FILE=".env"
append_env() {
  local key="$1"
  local value="$2"
  if ! grep -q "^${key}=" "${ENV_FILE}" 2>/dev/null; then
    echo "${key}=${value}" >> "${ENV_FILE}"
  fi
}

if [ -f "${ENV_FILE}" ]; then
  append_env "BARBACOA_PRINTER_DEVICE" "/dev/usb/lp0"
  append_env "BARBACOA_PRINTER_AUTOPRINT" "true"
else
  echo "WARN: .env not found; skipping printer defaults."
fi

echo "Pulling updates..."
git pull

echo "Installing deps..."
source .venv/bin/activate
pip install -r requirements.txt

echo "Restarting POS..."
sudo systemctl restart barbacoa-pos

echo "Update complete."
