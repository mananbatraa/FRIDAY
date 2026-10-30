#!/bin/bash
# Phone alerts 30 minutes before anything is due or starts (Canvas, calendars, interviews, dated to-dos).
#   ./scripts/alerts_mac.sh        check every 5 minutes while the Mac is awake
#   ./scripts/alerts_mac.sh off    turn it off
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
LABEL="com.friday.alerts"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = "off" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Deadline alerts are off."
  exit 0
fi

mkdir -p "$DIR/logs"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/.venv/bin/python</string>
    <string>-m</string><string>tracker.deadlines</string>
  </array>
  <key>StartInterval</key><integer>300</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DIR/logs/alerts.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/alerts.log</string>
</dict>
</plist>
PLIST
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Deadline alerts are on: checked every 5 minutes, sent 30 minutes before. Log: $DIR/logs/alerts.log"
