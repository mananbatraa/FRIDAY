#!/bin/bash
# Open new job postings for Tsenta automatically every 3 hours while your Mac is awake.
#   ./scripts/schedule_jobs_mac.sh          turn it on
#   ./scripts/schedule_jobs_mac.sh off      turn it off
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
LABEL="com.friday.openjobs"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = "off" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Automatic job opening is off."
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
    <string>-m</string><string>tracker.open_jobs</string>
    <string>--batch</string><string>10</string>
    <string>--browser</string><string>Google Chrome</string>
    <string>--max-age</string><string>3</string>
    <string>--wait</string><string>120</string>
    <string>--close</string>
    <string>--skip-no-sponsor</string>
    <string>--skip-citizen</string>
    <string>--us-only</string>
    <string>--section</string><string>swe</string>
    <string>--section</string><string>ai</string>
  </array>
  <key>StartInterval</key><integer>10800</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DIR/logs/open_jobs.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/open_jobs.log</string>
</dict>
</plist>
PLIST
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Automatic job opening is on: every 3 hours while your Mac is awake, starting now."
echo "New postings open in Chrome 10 at a time, 2 minutes per batch. Log: $DIR/logs/open_jobs.log"
