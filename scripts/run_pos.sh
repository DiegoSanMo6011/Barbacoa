#!/usr/bin/env bash
set -euo pipefail

LOG="/home/adminbbq/barbacoa_pos/pos_autostart.log"
VENV_PY="/home/adminbbq/barbacoa_pos/.venv/bin/python"
HOST="rwbzbaenzfqnstxsuxrl.supabase.co"

echo "=== POS autostart $(date) ===" >> "$LOG"
echo "USER=$(whoami) DISPLAY=${DISPLAY:-} XDG_SESSION_DESKTOP=${XDG_SESSION_DESKTOP:-} PWD=$(pwd)" >> "$LOG"

cd /home/adminbbq/barbacoa_pos || exit 1

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: venv python not found at $VENV_PY" >> "$LOG"
  exit 1
fi

echo "Using python: $VENV_PY - $($VENV_PY -V)" >> "$LOG"

echo "Waiting for network/DNS..." >> "$LOG"
i=1
while [ $i -le 60 ]; do
  # DNS listo?
  if getent hosts "$HOST" >/dev/null 2>&1; then
    echo "DNS OK ($HOST)" >> "$LOG"
    break
  fi
  echo "  DNS not ready yet... ($i/60)" >> "$LOG"
  sleep 2
  i=$((i+1))
done

# Si aún no hay DNS, no revientes el sistema en loop infinito: reintenta luego
if ! getent hosts "$HOST" >/dev/null 2>&1; then
  echo "DNS still not ready after wait. Exiting so autostart can retry next login." >> "$LOG"
  exit 0
fi

"$VENV_PY" /home/adminbbq/barbacoa_pos/app/main.py >> "$LOG" 2>&1

