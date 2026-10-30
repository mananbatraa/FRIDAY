"""Text yourself a list of what's pending: interview rounds, to-dos, next steps and outreach follow-ups.

    python -m tracker.reminder            # send the reminder
    python -m tracker.reminder --print    # just print it

It reads the same tables as the dashboard and changes nothing. Nothing pending,
no message. Run ./scripts/remind_mac.sh to get it at set times every day.

Where it goes (the first one set up in .env):
- With WHATSAPP_PHONE and CALLMEBOT_APIKEY, to your WhatsApp through CallMeBot
  (callmebot.com, free): a normal notification on your phone. CallMeBot sees
  the message text.
- With TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env, to your Telegram bot:
  a normal notification on your phone, free.
- Otherwise as an iMessage to REMINDER_PHONE, through the Messages app on your
  Mac. If the Mac is signed in to iMessage with that same number, the text
  lands in your thread with yourself, usually without an alert.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

from .job_emails import REJECTED
from .outreach import FOLLOW_UP_DUE

MAX_ITEMS = 8  # per section, so the text stays readable on a phone


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _day(d: date, today: date) -> str:
    if d == today:
        return "today"
    if d == today + timedelta(days=1):
        return "tomorrow"
    return d.strftime("%a %b %-d") if 0 < (d - today).days < 7 else d.strftime("%b %-d")


def _section(title: str, lines: list[str]) -> list[str]:
    if not lines:
        return []
    more = [f"  (and {len(lines) - MAX_ITEMS} more)"] if len(lines) > MAX_ITEMS else []
    return [f"{title} ({len(lines)})"] + [f"• {line}" for line in lines[:MAX_ITEMS]] + more


def pending(apps: list[dict], todos: list[dict], outreach_rows: list[dict], now: datetime,
            extra: list[tuple[str, list[str]]] = ()) -> str:
    """The reminder text, or "" when nothing is pending."""
    today = now.date()

    rounds = []
    for row in apps:
        if row.get("Status") == REJECTED:
            continue
        try:
            items = json.loads(row.get("Rounds") or "[]")
        except ValueError:
            continue
        for r in items if isinstance(items, list) else []:
            try:
                when = datetime.fromisoformat(r.get("When", ""))
            except (AttributeError, TypeError, ValueError):
                continue
            if now - timedelta(hours=1) <= when <= now + timedelta(hours=48):
                label = r.get("Round") or "Interview"
                rounds.append((when, f"{label} at {row['Company']}, {_day(when.date(), today)} {when:%-I:%M %p}"))
    rounds.sort()

    tasks = []
    for t in todos:
        if _date(t.get("Done", "")):
            continue
        due = _date(t.get("Due", ""))
        company = t.get("Company", "")
        text = t.get("Task", "") + (f" at {company}" if company and company not in t.get("Task", "") else "")
        if due and due < today:
            text += f" (overdue, was due {_day(due, today)})"
        elif due:
            text += f" (due {_day(due, today)})"
        tasks.append((due or date.max, text))
    for row in apps:
        if row.get("Next action") and row.get("Status") != REJECTED:
            tasks.append((date.max, f"{row['Next action']} at {row['Company']}"))
    tasks.sort(key=lambda t: t[0])

    follow_ups = [f"{r.get('Name') or r.get('Email')}" + (f" ({r['Company']})" if r.get("Company") else "")
                  for r in sorted(outreach_rows, key=lambda r: r.get("Sent on", ""))
                  if r.get("Status") == FOLLOW_UP_DUE]

    sections = dict(extra)  # today, this week, emails to answer, stock app (see tracker/daily.py)
    body = (_section("Today", sections.pop("Today", []))
            + _section("Interviews in the next 48 hours", [t for _, t in rounds])
            + _section("To-dos", [t for _, t in tasks])
            + _section("Due this week", sections.pop("Due this week", []))
            + _section("Emails waiting on your reply", sections.pop("Emails waiting on your reply", []))
            + _section("Outreach follow-ups due", follow_ups))
    for title, lines in sections.items():
        body += _section(title, lines)
    if not body:
        return ""
    return "\n".join([f"FRIDAY: pending for {now:%a %b %-d}"] + body)


def send_imessage(phone: str, text: str) -> None:
    """Send `text` from the Messages app on this Mac. Raises RuntimeError if Messages refuses."""
    script = """on run {target, msg}
    tell application "Messages"
        set svc to 1st account whose service type = iMessage
        send msg to participant target of svc
    end tell
end run"""
    result = subprocess.run(["osascript", "-e", script, phone, text], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Messages couldn't send the text")


def send_whatsapp(phone: str, apikey: str, text: str) -> None:
    """Send `text` to your own WhatsApp through CallMeBot. Raises OSError or RuntimeError if it refuses."""
    query = urllib.parse.urlencode({"phone": phone, "text": text, "apikey": apikey})
    with urllib.request.urlopen(f"https://api.callmebot.com/whatsapp.php?{query}", timeout=60) as response:
        body = response.read().decode("utf-8", "replace")
    # CallMeBot answers 200 with an HTML page either way; errors say so in the text.
    if "error" in body.lower() and "queued" not in body.lower():
        raise RuntimeError("CallMeBot didn't accept the message (check WHATSAPP_PHONE and CALLMEBOT_APIKEY)")


def send_telegram(token: str, chat_id: str, text: str) -> None:
    """Send `text` from your Telegram bot. Raises OSError or RuntimeError if Telegram refuses."""
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=30) as response:
        if not json.load(response).get("ok"):
            raise RuntimeError("Telegram didn't accept the message")


def load_rows():
    from .config import Config
    from .storage import open_outreach_table, open_tables, open_todo_table

    config = Config.load()
    creds = None
    if config.sheet_id:
        from .google_auth import get_credentials

        creds = get_credentials(config.credentials_file, config.token_file, interactive=False)
    app_table, _ = open_tables(creds, config.sheet_id)
    todo_table = open_todo_table(creds, config.sheet_id)
    # Same rule as the dashboard: don't add an empty Outreach tab until tracking is on.
    outreach_table = open_outreach_table(creds, config.sheet_id) if config.outreach_query or not config.sheet_id \
        else None
    return app_table.load(), todo_table.load(), outreach_table.load() if outreach_table else []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--print", action="store_true", help="print the reminder instead of texting it")
    args = parser.parse_args(argv)

    from .google_auth import LoginNeeded
    from .notify import notify, send_ntfy

    try:
        apps, todos, outreach_rows = load_rows()
    except LoginNeeded as e:
        print(e)
        notify("FRIDAY needs you", str(e))
        return 1
    from .daily import extra_sections

    now = datetime.now()
    text = pending(apps, todos, outreach_rows, now, extra_sections(now, apps, todos))
    if args.print:
        print(text or "Nothing pending.")
        return 0
    if not text:
        print("Nothing pending, no text sent.")
        return 0
    whatsapp = os.environ.get("WHATSAPP_PHONE", "").strip()
    apikey = os.environ.get("CALLMEBOT_APIKEY", "").strip()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    phone = os.environ.get("REMINDER_PHONE", "").strip()
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    try:
        if whatsapp and apikey:
            send_whatsapp(whatsapp, apikey, text)
            where = f"WhatsApp {whatsapp}"
        elif topic:  # a real phone alert, unlike an iMessage to your own number
            send_ntfy(topic, "FRIDAY: what's pending", text)
            where = "ntfy"
        elif token and chat_id:
            send_telegram(token, chat_id, text)
            where = "Telegram"
        elif phone:
            send_imessage(phone, text)
            where = phone
        else:
            print("Set WHATSAPP_PHONE and CALLMEBOT_APIKEY, TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, or "
                  "REMINDER_PHONE in .env to get this sent to you:\n\n" + text)
            return 1
    except (OSError, RuntimeError) as e:
        print(f"Couldn't send the reminder: {e}")
        notify("FRIDAY couldn't reach you", str(e))
        return 1
    print(f"Sent to {where}:\n\n{text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
