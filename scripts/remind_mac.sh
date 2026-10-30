#!/bin/bash
# Text yourself what's pending (set REMINDER_PHONE in .env first).
#   ./scripts/remind_mac.sh                          every day at 9:00
#   ./scripts/remind_mac.sh 9:00 12:00 16:00 19:00   at each of these times (24-hour clock)
#   ./scripts/remind_mac.sh off                      turn it off
# If your Mac is asleep at one of the times, that text goes out when it wakes up.
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

TIMES=("$@")
[ ${#TIMES[@]} -eq 0 ] && TIMES=(9:00)
SLOTS=""
for TIME in "${TIMES[@]}"; do
  HOUR="${TIME%%:*}"
  MINUTE="${TIME#*:}"
  [ "$MINUTE" = "$TIME" ] && MINUTE=0
  if ! [[ "$HOUR" =~ ^[0-9]+$ && "$MINUTE" =~ ^[0-9]+$ ]] || [ "$((10#$HOUR))" -gt 23 ] || [ "$((10#$MINUTE))" -gt 59 ]; then
    echo "Give times on the 24-hour clock, like 9:00 or 16:30 (not \"$TIME\")."
    exit 1
  fi
  SLOTS="$SLOTS
    <dict><key>Hour</key><integer>$((10#$HOUR))</integer><key>Minute</key><integer>$((10#$MINUTE))</integer></dict>"
  WHEN="$WHEN$(printf ' %d:%02d' "$((10#$HOUR))" "$((10#$MINUTE))")"
done
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
  <array>$SLOTS
  </array>
  <key>StandardOutPath</key><string>$DIR/logs/reminder.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/reminder.log</string>
</dict>
</plist>
PLIST
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Reminder texts are on, every day at$WHEN. Log: $DIR/logs/reminder.log"
