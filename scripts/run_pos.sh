#!/usr/bin/env bash
set -uo pipefail

BASE="/home/adminbbq/barbacoa_pos"
LOG="$BASE/pos_autostart.log"
VENV_PY="$BASE/.venv/bin/python"

# El host a esperar se deriva del .env para que no se desincronice del
# proyecto Supabase real. Antes estaba hardcodeado a un proyecto que ya no
# existe, su DNS nunca resolvia y el POS jamas arrancaba por autostart.
HOST="$(grep -E '^SUPABASE_URL=' "$BASE/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'\'' ' | sed -E 's|^https?://||; s|/.*$||')"
[ -n "$HOST" ] || HOST="kcknttjnubjlrljzptda.supabase.co"

# Rotacion: sin esto el log crecia sin limite (llego a 3.5 MB de reintentos).
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 2097152 ]; then
  mv -f "$LOG" "$LOG.1"
fi

echo "=== POS autostart $(date) ===" >> "$LOG"
echo "USER=$(whoami) DISPLAY=${DISPLAY:-} XDG_SESSION_DESKTOP=${XDG_SESSION_DESKTOP:-} HOST=$HOST" >> "$LOG"

cd "$BASE" || exit 1

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: venv python not found at $VENV_PY" >> "$LOG"
  exit 1
fi

echo "Using python: $VENV_PY - $($VENV_PY -V 2>&1)" >> "$LOG"

# Espera hasta 60s a que haya DNS, pero NO es bloqueante: el POS es
# offline-first (cola SQLite local), asi que si la red del negocio esta
# caida igual debe abrir y operar, encolando lo que no pueda sincronizar.
echo "Esperando DNS ($HOST)..." >> "$LOG"
i=1
while [ $i -le 30 ]; do
  if getent hosts "$HOST" >/dev/null 2>&1; then
    echo "DNS OK ($HOST) tras $((i * 2))s" >> "$LOG"
    break
  fi
  sleep 2
  i=$((i + 1))
done

if ! getent hosts "$HOST" >/dev/null 2>&1; then
  echo "AVISO: sin DNS tras 60s. Se arranca igual en modo offline." >> "$LOG"
fi

echo "Lanzando POS..." >> "$LOG"
exec "$VENV_PY" "$BASE/app/main.py" >> "$LOG" 2>&1
