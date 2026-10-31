"""Text FRIDAY from your phone.

Send a message to the ntfy topic NTFY_INBOX_TOPIC (in the ntfy app, subscribe to it and type in
the box at the bottom). FRIDAY answers on NTFY_TOPIC within a few seconds:

    list            what's due today, tomorrow and this week (also "what's due?")
    pending         the same message as the morning report
    done <text>     mark the next item matching <text> done; "done all <text>" for every match
    undo <text>     not done after all
    todo <text>     add a to-do; end with a day ("tomorrow", "by fri", "nov 2") to give it a due date
    submit          remind you on the Mac to submit the hackathon report with Claude
    send <code>     send an email draft the assistant saved (cancel <code> deletes it)
    new             start a fresh conversation with the assistant
    help            this list

Anything else goes to Claude Code on this Mac (tracker/agent.py), which can only use tracker/tools.py;
with FRIDAY_ASSISTANT=off it gets the help text instead. Anyone who knows the inbox topic can send
these, so make it long and random, and different from NTFY_TOPIC.

    python -m tracker.inbox --listen  answer as messages arrive (launchd keeps this running)
    python -m tracker.inbox           answer what's arrived since last time, once
    python -m tracker.inbox --ask T   answer T here without ntfy, to try it out
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta

from .notify import NTFY_SERVER

STATE_FILE = "logs/inbox_state.json"  # the last message answered, so none is answered twice
MAX_REPLY = 3900  # ntfy turns longer messages (4096 bytes) into an attachment
HELP = ("Text me one of these:\n"
        "list: what's due this week\n"
        "pending: the morning report\n"
        "done <text>: mark it done (done all <text> for every match)\n"
        "undo <text>: not done after all\n"
        "todo <text> [tomorrow, by fri, nov 2]: add a to-do\n"
        "submit: remind me on the Mac to submit the hackathon report\n"
        "send / cancel <code>: send or delete an email draft I saved\n"
        "new: start a fresh conversation\n"
        "Anything else goes to Claude: \"email Sam the slides plan\", \"apply to <link>\"\n"
        "help: this list")
SLOW = {"pending"}  # these read Gmail too, so they get a quick "on it" first

_COMMANDS = {
    "list": "list", "today": "list", "week": "list", "due": "list", "deadlines": "list", "agenda": "list",
    "pending": "pending", "report": "pending", "morning": "pending",
    "done": "done", "undo": "undo", "todo": "todo",
    "send": "send", "cancel": "cancel",
    "submit": "submit", "new": "new",
    "help": "help", "commands": "help",
}
_ALONE = {"list", "pending", "submit", "new", "help"}  # only when that's the whole text: "list my applications" is for Claude
_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_WEEKDAY_NAMES = {"mon", "monday", "tue", "tues", "tuesday", "wed", "weds", "wednesday", "thu", "thur", "thurs",
                  "thursday", "fri", "friday", "sat", "saturday", "sun", "sunday"}
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def parse(text: str) -> tuple[str, str]:
    """(command, the rest) from what was typed: "Done HW3." -> ("done", "HW3")."""
    text = text.strip().rstrip(".!?").strip()
    words = text.split(maxsplit=1)
    if not words:
        return "help", ""
    rest = words[1].strip() if len(words) > 1 else ""
    first = re.sub(r"[^\w?]", "", words[0].lower()).rstrip("?")
    command = _COMMANDS.get(first)
    if command in _ALONE and not rest or command in ("done", "undo", "todo") \
            or command in ("send", "cancel") and re.fullmatch(r"\d{4}", rest):
        return command, rest
    if re.match(r"what('?s|\s+is)\s+(due|up|left|pending)", text.lower()):
        return "list", ""
    return "unknown", text


def parse_day(phrase: str, today: date) -> date | None:
    """today, tomorrow, fri, friday, nov 2, 2 november, 11/2 or 2026-11-02 as a date on or after today."""
    p = phrase.lower().strip(" .,!")
    if p in ("today", "tonight"):
        return today
    if p in ("tomorrow", "tmrw", "tmr", "tomorow"):
        return today + timedelta(days=1)
    if p in _WEEKDAY_NAMES:
        return today + timedelta(days=(_WEEKDAYS.index(p[:3]) - today.weekday()) % 7)
    try:
        return date.fromisoformat(p)
    except ValueError:
        pass
    month = day = None
    if m := re.fullmatch(r"([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?", p):
        month, day = m.group(1), m.group(2)
    elif m := re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})", p):
        day, month = m.group(1), m.group(2)
    elif m := re.fullmatch(r"(\d{1,2})/(\d{1,2})", p):
        month, day = _MONTHS[int(m.group(1)) - 1] if 1 <= int(m.group(1)) <= 12 else None, m.group(2)
    if not month or month[:3] not in _MONTHS:
        return None
    try:
        when = date(today.year, _MONTHS.index(month[:3]) + 1, int(day))
        return when if when >= today else when.replace(year=today.year + 1)
    except ValueError:
        return None


def parse_todo(text: str, today: date) -> tuple[str, str]:
    """(task, due date or "") from "call Josh by fri" or "call Josh tomorrow"."""
    words = text.split()
    for n in (2, 1):
        if len(words) <= n:
            continue
        when = parse_day(" ".join(words[-n:]), today)
        if when:
            task = words[:-n]
            if task[-1].lower() in ("by", "on", "due", "before") and len(task) > 1:
                task = task[:-1]
            return " ".join(task), when.isoformat()
    return text.strip(), ""


def answer(text: str, now: datetime) -> str:
    """FRIDAY's reply to one message."""
    command, rest = parse(text)

    if command == "list":
        from .deadlines import collect, report_sections
        from .reminder import load_rows

        apps, todos, _ = load_rows()
        items, problems = collect(apps, todos)
        lines = []
        for title, entries in report_sections(items, now):
            if entries:
                lines += [f"{title}:"] + [f"• {e}" for e in entries]
        return "\n".join(lines + problems) or "Nothing due this week."

    if command == "pending":
        from .daily import extra_sections
        from .reminder import load_rows, pending

        apps, todos, outreach_rows = load_rows()
        return pending(apps, todos, outreach_rows, now, extra_sections(now, apps, todos),
                       morning=now.hour < 12) or "Nothing pending."

    if command in ("done", "undo"):
        if not rest:
            return f"{command.capitalize()} what? Send part of its name, like: {command} hw3"
        return _done(rest, now.date(), undo=command == "undo")

    if command == "todo":
        if not rest:
            return "Add what? Like: todo email Josh by fri"
        task, due = parse_todo(rest, now.date())
        table = _todo_table()
        table.save(table.load() + [{"Task": task, "Due": due, "Source": "texted to FRIDAY"}])
        return f"Added: {task}" + (f" (due {date.fromisoformat(due):%a %b %-d})" if due else "")

    if command == "submit":
        from .notify import notify

        notify("FRIDAY: submit the hackathon report", "Asked from your phone. Tell Claude: submit", phone=False)
        return ("Noted. I can't fill the form from here: on the Mac, tell Claude \"submit\" "
                "and it writes and submits the report for you.")

    if command in ("send", "cancel"):
        from . import tools

        return tools.send(rest) if command == "send" else tools.cancel(rest)

    if command == "new":
        from . import agent

        agent.forget()
        return "Starting fresh. What do you need?"

    if command == "unknown":
        from . import agent

        if agent.available():
            return agent.ask(text, now)
        return f"I didn't get {rest!r}.\n\n{HELP}"
    return HELP


def _done(text: str, today: date, undo: bool) -> str:
    """Mark one item done (or not done), asking which when the words fit several different ones."""
    from .deadlines import collect, load_done, matching, set_done
    from .reminder import load_rows

    every = text.lower().startswith("all ")
    if every:
        text = text[4:]
    apps, todos, _ = load_rows()
    items, _ = collect(apps, todos, include_done=undo)
    if undo:
        done = load_done()
        items = [i for i in items if i.key in done]
    matches = matching(items, text, today)
    if not matches:
        return f"Nothing {'marked done' if undo else 'upcoming'} matches {text!r}. Send list to see what's there."
    titles = list(dict.fromkeys(i.title for i in matches))
    if len(titles) > 1 and not every:
        options = [next(i for i in matches if i.title == t).label(today) for t in titles]
        return ("Which one? Send more of its name:\n" + "\n".join(f"• {o}" for o in options[:10])
                + f"\nOr: {'undo' if undo else 'done'} all {text}")
    chosen = matches if every else matches[:1]  # a repeating item (the daily reports): only the next one
    set_done(chosen, today, done=not undo)
    word = "Not done" if undo else "Done"
    lines = [f"{word}: {i.label(today)}" for i in chosen]
    if not every and len(matches) > 1:
        lines.append(f"(The other {len(matches) - 1} like it are untouched.)")
    return "\n".join(lines)


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


def fetch(topic: str, since: str) -> list[dict]:
    """Messages on `topic` after `since` (a message id or a unix time), oldest first."""
    url = f"{NTFY_SERVER}/{topic}/json?poll=1&since={since}"
    with urllib.request.urlopen(url, timeout=20) as response:
        lines = response.read().decode("utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    return [e for e in events if e.get("event") == "message"]


def is_slow(text: str) -> bool:
    from . import agent

    command = parse(text)[0]
    return command in SLOW or command == "unknown" and agent.available()


def handle(message: dict, outbox: str, state: dict) -> bool:
    """Answer one message on `outbox`. False if the reply couldn't be sent (try again later)."""
    from .google_auth import LoginNeeded
    from .notify import send_ntfy

    text = message.get("message", "")
    try:
        if is_slow(text):
            send_ntfy(outbox, "FRIDAY", "On it, give me a few seconds…")
        try:
            reply = answer(text, datetime.now())
        except LoginNeeded as e:
            reply = str(e)
        except Exception as e:  # noqa: BLE001 - one bad message must not stop the inbox
            reply = f"Something went wrong: {type(e).__name__}: {e}"
        if len(reply.encode("utf-8")) > MAX_REPLY:
            reply = reply.encode("utf-8")[:MAX_REPLY].decode("utf-8", "ignore").rsplit("\n", 1)[0] + "\n…"
        print(f"{datetime.now():%Y-%m-%d %H:%M} {text!r} -> {reply.splitlines()[0] if reply else ''}", flush=True)
        send_ntfy(outbox, f"FRIDAY: {text[:40]}", reply)
    except OSError as e:
        print(f"Couldn't send the reply: {e}", flush=True)
        return False  # keep last_id, so this message is answered next time
    state["last_id"] = message["id"]
    _save_state(state)
    return True


def listen(inbox: str, outbox: str, state: dict) -> None:
    """Answer messages as they arrive, reconnecting (and catching up) after the Mac sleeps or the network drops."""
    while True:
        since = state.setdefault("last_id", str(int(time.time())))
        try:
            # ntfy sends a keepalive every ~45 seconds, so a silent minute means the connection is gone.
            with urllib.request.urlopen(f"{NTFY_SERVER}/{inbox}/json?since={since}", timeout=90) as stream:
                for line in stream:
                    event = json.loads(line) if line.strip() else {}
                    if event.get("event") == "message" and not handle(event, outbox, state):
                        break
        except (OSError, ValueError) as e:
            print(f"{datetime.now():%Y-%m-%d %H:%M} inbox connection: {e}", flush=True)
        time.sleep(10)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ask", metavar="TEXT", help="print FRIDAY's answer to TEXT instead of checking ntfy")
    parser.add_argument("--listen", action="store_true", help="keep running and answer messages as they arrive")
    args = parser.parse_args(argv)

    from .config import Config

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
    if args.listen:
        listen(inbox, outbox, state)
    # The first time, start from now rather than answering old messages.
    since = state.get("last_id") or str(int(time.time()))
    try:
        messages = fetch(inbox, since)
    except (OSError, ValueError) as e:
        print(f"Couldn't check the inbox: {e}")
        return 1
    for message in messages:
        if not handle(message, outbox, state):
            return 1
    if not messages and "last_id" not in state:
        state["last_id"] = since
        _save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
