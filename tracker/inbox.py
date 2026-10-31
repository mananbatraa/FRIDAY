"""Text FRIDAY from your phone.

Send a message to the ntfy topic NTFY_INBOX_TOPIC (in the ntfy app, subscribe to it and type in
the box at the bottom). Every minute this checks for new messages and answers on NTFY_TOPIC:

    list            what's due today, tomorrow and this week
    pending         the same message as the morning report
    done <text>     mark upcoming items whose title contains <text> as done
    todo <text>     add a to-do (end with "by YYYY-MM-DD" to give it a due date)
    help            this list

Only these commands run; anything else gets the help text back. Anyone who knows the inbox topic
can send them, so make it long and random, and different from NTFY_TOPIC.

    python -m tracker.inbox          check once (launchd runs this every minute)
    python -m tracker.inbox --ask T  answer T here without ntfy, to try it out
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime

from .notify import NTFY_SERVER

STATE_FILE = "logs/inbox_state.json"  # the last message answered, so none is answered twice
HELP = ("Text me one of these:\n"
        "list: due today, tomorrow and this week\n"
        "pending: the morning report\n"
        "done <text>: mark it done\n"
        "todo <text> [by YYYY-MM-DD]: add a to-do\n"
        "help: this list")


def fetch(topic: str, since: str) -> list[dict]:
    """Messages on `topic` after `since` (a message id or a unix time), oldest first."""
    url = f"{NTFY_SERVER}/{topic}/json?poll=1&since={since}"
    with urllib.request.urlopen(url, timeout=20) as response:
        lines = response.read().decode("utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    return [e for e in events if e.get("event") == "message"]


def parse_todo(text: str, today: date) -> tuple[str, str]:
    """(task, due date or "") from "call Josh by 2026-11-02"."""
    match = re.search(r"\s+by\s+(\d{4}-\d{2}-\d{2})\s*$", text)
    if match:
        try:
            date.fromisoformat(match.group(1))
            return text[:match.start()].strip(), match.group(1)
        except ValueError:
            pass
    return text.strip(), ""


def answer(text: str, now: datetime) -> str:
    """FRIDAY's reply to one message."""
    command, _, rest = text.strip().partition(" ")
    command, rest = command.lower(), rest.strip()

    if command in ("list", "today", "week"):
        from .deadlines import collect, report_sections
        from .reminder import load_rows

        apps, todos, _ = load_rows()
        items, problems = collect(apps, todos)
        lines = []
        for title, entries in report_sections(items, now):
            if entries:
                lines += [f"{title}:"] + [f"• {e}" for e in entries]
        return "\n".join(lines + problems) or "Nothing due this week."

    if command in ("pending", "report"):
        from .daily import extra_sections
        from .reminder import load_rows, pending

        apps, todos, outreach_rows = load_rows()
        return pending(apps, todos, outreach_rows, now, extra_sections(now, apps, todos),
                       morning=now.hour < 12) or "Nothing pending."

    if command == "done" and rest:
        from .deadlines import collect, mark_done
        from .reminder import load_rows

        apps, todos, _ = load_rows()
        items, _ = collect(apps, todos)
        matched = mark_done(items, rest, now.date())
        return "\n".join(f"Done: {i.label(now.date())}" for i in matched) or f"Nothing upcoming matches {rest!r}."

    if command == "todo" and rest:
        task, due = parse_todo(rest, now.date())
        table = _todo_table()
        table.save(table.load() + [{"Task": task, "Due": due, "Source": "texted to FRIDAY"}])
        return f"Added: {task}" + (f" (due {due})" if due else "")

    return HELP


def _todo_table():
    from .config import Config
    from .storage import open_todo_table

    config = Config.load()
    creds = None
    if config.sheet_id:
        from .google_auth import get_credentials

        creds = get_credentials(config.credentials_file, config.token_file, interactive=False)
    return open_todo_table(creds, config.sheet_id)


def _load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ask", metavar="TEXT", help="print FRIDAY's answer to TEXT instead of checking ntfy")
    args = parser.parse_args(argv)

    from .config import Config
    from .google_auth import LoginNeeded
    from .notify import send_ntfy

    Config.load()
    if args.ask:
        print(answer(args.ask, datetime.now()))
        return 0

    inbox = os.environ.get("NTFY_INBOX_TOPIC", "").strip()
    outbox = os.environ.get("NTFY_TOPIC", "").strip()
    if not inbox or not outbox:
        print("Set NTFY_INBOX_TOPIC and NTFY_TOPIC in .env to text FRIDAY from your phone.")
        return 1
    if inbox == outbox:
        print("NTFY_INBOX_TOPIC must be different from NTFY_TOPIC, or FRIDAY would answer its own replies.")
        return 1

    state = _load_state()
    # The first time, start from now rather than answering old messages.
    since = state.get("last_id") or str(int(time.time()))
    try:
        messages = fetch(inbox, since)
    except (OSError, ValueError) as e:
        print(f"Couldn't check the inbox: {e}")
        return 1
    for message in messages:
        text = message.get("message", "")
        try:
            reply = answer(text, datetime.now())
        except LoginNeeded as e:
            reply = str(e)
        print(f"{datetime.now():%Y-%m-%d %H:%M} {text!r} -> {reply.splitlines()[0] if reply else ''}")
        try:
            send_ntfy(outbox, f"FRIDAY: {text[:40]}", reply)
        except OSError as e:
            print(f"Couldn't send the reply: {e}")
            return 1  # keep last_id, so this message is answered next time
        state["last_id"] = message["id"]
        _save_state(state)
    if not messages and "last_id" not in state:
        state["last_id"] = since
        _save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
