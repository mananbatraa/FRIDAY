"""Text yourself a list of what's pending: interview rounds, to-dos, next steps and outreach follow-ups.

    python -m tracker.reminder            # send the reminder as an iMessage to REMINDER_PHONE
    python -m tracker.reminder --print    # just print it

It reads the same tables as the dashboard and changes nothing. The text goes
out through the Messages app on your Mac, so it's free and needs no account
beyond the Apple ID you're already signed in with. Nothing pending, no text.
Run ./scripts/remind_mac.sh to get it every morning.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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


def pending(apps: list[dict], todos: list[dict], outreach_rows: list[dict], now: datetime) -> str:
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

    body = (_section("Interviews in the next 48 hours", [t for _, t in rounds])
            + _section("To-dos", [t for _, t in tasks])
            + _section("Outreach follow-ups due", follow_ups))
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
    from .notify import notify

    try:
        apps, todos, outreach_rows = load_rows()
    except LoginNeeded as e:
        print(e)
        notify("FRIDAY needs you", str(e))
        return 1
    text = pending(apps, todos, outreach_rows, datetime.now())
    if args.print:
        print(text or "Nothing pending.")
        return 0
    if not text:
        print("Nothing pending, no text sent.")
        return 0
    phone = os.environ.get("REMINDER_PHONE", "").strip()
    if not phone:
        print("Set REMINDER_PHONE in .env (e.g. +14805551234) to get this as a text:\n\n" + text)
        return 1
    try:
        send_imessage(phone, text)
    except (OSError, RuntimeError) as e:
        print(f"Couldn't send the text: {e}")
        notify("FRIDAY couldn't text you", str(e))
        return 1
    print(f"Texted {phone}:\n\n{text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
