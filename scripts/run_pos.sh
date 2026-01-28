#!/usr/bin/env bash
set -e

LOG="/home/adminbbq/barbacoa_pos/pos_autostart.log"

echo "=== POS autostart $(date) ===" >> "$LOG"
echo "USER=$(whoami) DISPLAY=${DISPLAY:-<empty>} XDG_SESSION_DESKTOP=${XDG_SESSION_DESKTOP:-<empty>} PWD=$(pwd)" >> "$LOG"

cd /home/adminbbq/barbacoa_pos
source .venv/bin/activate

echo "Using python: $(which python) - $(python -V)" >> "$LOG"
python app/main.py >> "$LOG" 2>&1

