#!/bin/bash
# FRIDAY setup: one script from a fresh download to everything running on a Mac.
#
#   ./setup.sh            guided setup (safe to run again; it skips what's already done)
#   ./setup.sh --status   show what's set up and what's running, change nothing
#
# It never sends email, never applies to jobs, and asks before turning on anything
# that runs in the background.
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
PY="$DIR/.venv/bin/python"

bold() { printf "\n\033[1m%s\033[0m\n" "$1"; }
ok() { printf "  \033[32m✓\033[0m %s\n" "$1"; }
todo() { printf "  \033[33m•\033[0m %s\n" "$1"; }
ask() { local reply; read -r -p "  $1 [y/N] " reply; [[ "$reply" =~ ^[Yy] ]]; }
setting() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2-; }
setting_or() { local v; v="$(setting "$1")"; echo "${v:-$2}"; }  # setting_or KEY DEFAULT
set_setting() {  # set_setting KEY VALUE: replace the line, or add it
  local key="$1" value="$2"
  if grep -qE "^#? ?$key=" .env; then
    KEY="$key" VALUE="$value" "$PY" - <<'EOF'
import os, re
key, value = os.environ["KEY"], os.environ["VALUE"]
text = open(".env").read()
text, n = re.subn(rf"^# ?{re.escape(key)}=.*$|^{re.escape(key)}=.*$", f"{key}={value}", text, count=1, flags=re.M)
open(".env", "w").write(text)
EOF
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}
running() { launchctl list 2>/dev/null | grep -q "$1"; }

status() {
  bold "FRIDAY status"
  [ -x "$PY" ] && ok "Python environment" || todo "Python environment: run ./setup.sh"
  [ -f .env ] && ok ".env settings" || todo ".env settings: run ./setup.sh"
  if [ -f "$(setting_or GOOGLE_CREDENTIALS_FILE credentials.json)" ]; then ok "Google Cloud app file"
  else todo "Google Cloud app file ($(setting_or GOOGLE_CREDENTIALS_FILE credentials.json)): see the README"; fi
  [ -f "$(setting_or GOOGLE_TOKEN_FILE token.json)" ] && ok "Main Gmail logged in" || todo "Main Gmail not logged in"
  for a in $(setting ALSO_READ_GMAIL | tr ',' ' '); do
    f="token_$(echo "${a%@*}" | tr '.' '_').json"; [ -f "$f" ] && ok "Also reading $a" || todo "$a not logged in yet"
  done
  [ -n "$(setting OUTREACH_QUERY)" ] && ok "Outreach tracking" || todo "Outreach tracking off (OUTREACH_QUERY)"
  [ -n "$(setting CANVAS_ICS_URL)" ] && ok "Canvas connected" || todo "Canvas not connected (CANVAS_ICS_URL)"
  [ -n "$(setting CALENDAR_ICS_URLS)" ] && ok "Calendars connected" || todo "No calendars (CALENDAR_ICS_URLS)"
  [ -n "$(setting STOCKS_DIR)" ] && ok "Stock app connected" || todo "Stock app not connected (STOCKS_DIR)"
  [ -n "$(setting NTFY_TOPIC)$(setting CALLMEBOT_APIKEY)$(setting TELEGRAM_BOT_TOKEN)" ] \
    && ok "Phone notifications" || todo "Phone notifications not set up (NTFY_TOPIC)"
  bold "Running in the background"
  for job in "jobtracker:Email check every 3 hours" "reminder:Morning message and evening list" \
             "alerts:Alerts 30 min before deadlines" "openjobs:Job opener every 3 hours"; do
    running "com.friday.${job%%:*}" && ok "${job#*:}" || todo "${job#*:}: off"
  done
  echo
}

if [ "$1" = "--status" ]; then
  status
  exit 0
fi

bold "1/7  Python"
if ! command -v python3 >/dev/null; then
  todo "Python 3 isn't installed. Install it from https://www.python.org/downloads/ and run ./setup.sh again."
  exit 1
fi
if [ ! -x "$PY" ]; then
  python3 -m venv .venv
fi
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt
ok "$("$PY" --version) with FRIDAY's packages in .venv"

bold "2/7  Settings"
if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example"
else
  ok ".env already exists (kept as it is)"
fi
if [ -z "$(setting FRIDAY_NAME)" ]; then
  read -r -p "  What should FRIDAY call you? " name
  [ -n "$name" ] && set_setting FRIDAY_NAME "$name" && ok "Hi, $name"
fi

bold "3/7  Google (Gmail)"
CREDS="$(setting_or GOOGLE_CREDENTIALS_FILE credentials.json)"
if [ ! -f "$CREDS" ]; then
  todo "FRIDAY needs a Google Cloud app file to read your Gmail. One time, about 10 minutes:"
  echo "     1. console.cloud.google.com > create a project > enable the Gmail API"
  echo "     2. Google Auth Platform > Audience: External; add your Gmail as a test user"
  echo "        (or click Publish app so the login doesn't expire every 7 days)"
  echo "     3. Clients > Create client > Desktop app > download the JSON"
  echo "     4. Save it in $DIR as $CREDS, then run ./setup.sh again"
  exit 1
fi
ok "Google Cloud app file: $CREDS"
if [ ! -f "$(setting_or GOOGLE_TOKEN_FILE token.json)" ]; then
  echo "  A browser window opens: pick your Gmail and allow access."
  "$PY" -m tracker.main --dry-run --days 7 >/dev/null
fi
ok "Main Gmail logged in"
if [ -z "$(setting ALSO_READ_GMAIL)" ] && ask "Read job emails from another Gmail too (e.g. your university one)?"; then
  read -r -p "  Its address: " extra
  [ -n "$extra" ] && set_setting ALSO_READ_GMAIL "$extra"
fi
for a in $(setting ALSO_READ_GMAIL | tr ',' ' '); do
  f="token_$(echo "${a%@*}" | tr '.' '_').json"
  if [ ! -f "$f" ]; then
    echo "  A browser window opens: pick $a and allow access."
    "$PY" -c "
from tracker.config import Config
from tracker.google_auth import get_credentials
for address, token, creds in Config.load().accounts():
    if address == '$a':
        get_credentials(creds, token, interactive=True, account=address)"
  fi
  ok "Also reading $a"
done

bold "4/7  Your day: Canvas, calendars, stocks"
if [ -z "$(setting CANVAS_ICS_URL)" ]; then
  echo "  Canvas > Calendar > \"Calendar Feed\" (bottom right) gives a private link. Paste it, or press Enter to skip."
  read -r -p "  Canvas link: " url
  [ -n "$url" ] && set_setting CANVAS_ICS_URL "$url" && ok "Canvas connected"
else
  ok "Canvas connected"
fi
if [ -z "$(setting CALENDAR_ICS_URLS)" ]; then
  echo "  Google Calendar > Settings > your calendar > Integrate calendar > \"Secret address in iCal format\"."
  echo "  Paste one or more links separated by commas, or press Enter to skip."
  read -r -p "  Calendar links: " urls
  [ -n "$urls" ] && set_setting CALENDAR_ICS_URLS "$urls" && ok "Calendars connected"
else
  ok "Calendars connected"
fi
if [ -z "$(setting STOCKS_DIR)" ] && [ -d "$HOME/Projects/stock-research" ] && ask "Add the stock-research app to the morning message?"; then
  set_setting STOCKS_DIR "$HOME/Projects/stock-research" && ok "Stock app connected"
fi

bold "5/7  Phone notifications (ntfy)"
if [ -z "$(setting NTFY_TOPIC)" ]; then
  topic="friday-$(whoami | tr -cd 'a-z0-9')-$(openssl rand -hex 6)"
  set_setting NTFY_TOPIC "$topic"
  echo "  1. Install the free \"ntfy\" app on your phone and allow notifications."
  echo "  2. Tap + and subscribe to this topic (keep it private):"
  printf "\n       \033[1m%s\033[0m\n\n" "$topic"
  read -r -p "  Press Enter once you've subscribed, and FRIDAY will send a test. "
fi
"$PY" -c "
import os
from tracker.config import Config; Config.load()
from tracker.notify import send_ntfy
send_ntfy(os.environ['NTFY_TOPIC'], 'FRIDAY', 'Setup test: notifications reach your phone.')" \
  && ok "Test notification sent to topic $(setting NTFY_TOPIC)"

bold "6/7  First email check"
"$PY" -m tracker.main --days "$(setting_or DAYS 30)" | tail -4

bold "7/7  Background jobs (they run while your Mac is awake)"
ask "Check email every 3 hours?" && ./scripts/schedule_mac.sh
ask "Morning message at 8:00 and a list at 18:00?" && ./scripts/remind_mac.sh 8:00 18:00
ask "Alerts 30 minutes before deadlines, classes and calls?" && ./scripts/alerts_mac.sh
if ask "Open new job postings every 3 hours for Tsenta's Chrome extension to apply? (only if you use Tsenta)"; then
  ./scripts/schedule_jobs_mac.sh
fi

status
echo "Double-click FRIDAY.command any time to check email and open the dashboard."
echo "Preview the morning message: .venv/bin/python -m tracker.reminder --print"
