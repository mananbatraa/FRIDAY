#!/bin/bash
# Text FRIDAY from your phone: checks NTFY_INBOX_TOPIC for new messages and answers on NTFY_TOPIC.
#   ./scripts/inbox_mac.sh         answer within seconds while the Mac is awake
#   ./scripts/inbox_mac.sh off     turn it off
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
LABEL="com.friday.inbox"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = "off" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Texting FRIDAY is off."
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
    <string>-m</string><string>tracker.inbox</string><string>--listen</string>
  </array>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DIR/logs/inbox.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/inbox.log</string>
</dict>
</plist>
PLIST
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Texting FRIDAY is on: it answers within seconds. Log: $DIR/logs/inbox.log"
