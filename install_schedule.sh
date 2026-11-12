#!/bin/bash
# Installs (or removes) a macOS LaunchAgent that runs the bot every weekday at
# 10:05 New York time (35 min after the US open), converted to this Mac's clock.
#   bash install_schedule.sh          install
#   bash install_schedule.sh --remove uninstall
set -euo pipefail
BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.tradingbot.daily"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ "${1:-}" == "--remove" ]]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Removed $LABEL"
  exit 0
fi

PY="$(command -v python3)"
REAL_PY="$("$PY" -c 'import sys; print(sys.executable)')"
mkdir -p "$BOT_DIR/logs" "$HOME/Library/LaunchAgents"
read -r HOUR MINUTE < <("$PY" - <<'PYEOF'
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    ny = datetime.now(ZoneInfo("America/New_York")).replace(hour=10, minute=5, second=0, microsecond=0)
    local = ny.astimezone()
    print(local.hour, local.minute)
except Exception:
    print(10, 5)
PYEOF
)

{
  echo '<?xml version="1.0" encoding="UTF-8"?>'
  echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
  echo '<plist version="1.0"><dict>'
  echo "  <key>Label</key><string>$LABEL</string>"
  echo '  <key>ProgramArguments</key><array>'
  echo "    <string>$REAL_PY</string><string>$BOT_DIR/run.py</string><string>daily</string>"
  echo '  </array>'
  echo "  <key>WorkingDirectory</key><string>$BOT_DIR</string>"
  echo '  <key>StartCalendarInterval</key><array>'
  for d in 1 2 3 4 5; do
    echo "    <dict><key>Weekday</key><integer>$d</integer><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MINUTE</integer></dict>"
  done
  echo '  </array>'
  echo "  <key>StandardOutPath</key><string>$BOT_DIR/logs/daily.log</string>"
  echo "  <key>StandardErrorPath</key><string>$BOT_DIR/logs/daily.err</string>"
  echo '</dict></plist>'
} > "$PLIST"

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed $LABEL: weekdays at $(printf '%02d:%02d' $HOUR $MINUTE) on this Mac's clock (= 10:05 New York). Logs in $BOT_DIR/logs/"
echo "If you change time zone (e.g. fly to the US), run this script again so it stays 10:05 New York."
echo
echo "IMPORTANT: your vault is on the Desktop, which macOS protects from background jobs."
echo "Give this Python Full Disk Access (System Settings > Privacy & Security > Full Disk Access > +,"
echo "then Cmd+Shift+G and paste):"
echo "    $REAL_PY"
echo
echo "Test it now with:  launchctl start $LABEL ; sleep 20 ; tail $BOT_DIR/logs/daily.log"
