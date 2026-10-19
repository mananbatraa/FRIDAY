#!/bin/bash
# Check for job updates automatically every 3 hours while your Mac is awake.
#   ./scripts/schedule_mac.sh          turn it on
#   ./scripts/schedule_mac.sh off      turn it off
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
LABEL="com.friday.jobtracker"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = "off" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Automatic checks are off."
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs"
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
    <string>-m</string><string>tracker.main</string>
    <string>--background</string><string>--days</string><string>14</string>
  </array>
  <key>StartInterval</key><integer>10800</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DIR/logs/tracker.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/tracker.log</string>
</dict>
</plist>
PLIST
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Automatic checks are on: every 3 hours while your Mac is awake."
echo "You'll get a notification when an application changes. Log: $DIR/logs/tracker.log"
