#!/bin/bash
# Text yourself what's pending every morning (set REMINDER_PHONE in .env first).
#   ./scripts/remind_mac.sh            every day at 9:00
#   ./scripts/remind_mac.sh 8:30       every day at 8:30
#   ./scripts/remind_mac.sh off        turn it off
# If your Mac is asleep at that time, the text goes out when it wakes up.
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
LABEL="com.friday.reminder"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = "off" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Daily reminder texts are off."
  exit 0
fi

TIME="${1:-9:00}"
HOUR="${TIME%%:*}"
MINUTE="${TIME#*:}"
[ "$MINUTE" = "$TIME" ] && MINUTE=0
if ! [[ "$HOUR" =~ ^[0-9]+$ && "$MINUTE" =~ ^[0-9]+$ ]] || [ "$HOUR" -gt 23 ] || [ "$MINUTE" -gt 59 ]; then
  echo "Give a time like 9:00 or 18:30."
  exit 1
fi
if ! grep -q "^REMINDER_PHONE=." .env 2>/dev/null; then
  echo "Put your phone number in .env first, e.g. REMINDER_PHONE=+14805551234"
  exit 1
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
    <string>-m</string><string>tracker.reminder</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$((10#$HOUR))</integer><key>Minute</key><integer>$((10#$MINUTE))</integer></dict>
  <key>StandardOutPath</key><string>$DIR/logs/reminder.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/reminder.log</string>
</dict>
</plist>
PLIST
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
printf "Daily reminder texts are on: every day at %d:%02d. Log: %s/logs/reminder.log\n" "$((10#$HOUR))" "$((10#$MINUTE))" "$DIR"
