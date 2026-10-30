"""More of your day for the reminder: Canvas assignments, emails waiting on your reply, and the stock app.

Each function returns plain lines for one reminder section, and returns [] when it isn't set up
or can't be reached, so one broken source never stops the reminder.

- Canvas: CANVAS_ICS_URL in .env, the "Calendar Feed" link from Canvas (Calendar, bottom right).
- Emails to answer: every Gmail account FRIDAY reads (see ALSO_READ_GMAIL).
- Stock app: STOCKS_DIR in .env, the stock-research folder; reads its paper/*.json files.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path

# ---------------------------------------------------------------- Canvas


def _unfold(ics: str) -> list[str]:
    """iCalendar wraps long lines with a leading space on the next one."""
    lines: list[str] = []
    for raw in ics.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _ics_when(value: str) -> datetime | None:
    value = value.strip()
    try:
        if len(value) == 8:  # all-day: 20261103
            return datetime.strptime(value, "%Y%m%d")
        if value.endswith("Z"):
            utc = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            return utc.astimezone().replace(tzinfo=None)
        return datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    except ValueError:
        return None


def parse_ics(ics: str) -> list[tuple[datetime, str]]:
    """(due, title) for every event in an iCalendar feed."""
    events, current = [], None
    for line in _unfold(ics):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            when = _ics_when(current.get("DTEND") or current.get("DTSTART") or "")
            if when and current.get("SUMMARY"):
                events.append((when, current["SUMMARY"]))
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.split(";")[0]] = value.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ")
    return events


def canvas_tasks(ics: str, now: datetime, days: int = 7) -> list[str]:
    """Assignments and events due from now to `days` ahead, soonest first."""
    soon = sorted(e for e in parse_ics(ics) if now - timedelta(hours=1) <= e[0] <= now + timedelta(days=days))
    out = []
    for when, title in soon:
        day = "today" if when.date() == now.date() else \
            "tomorrow" if when.date() == now.date() + timedelta(days=1) else when.strftime("%a %b %-d")
        time = "" if (when.hour, when.minute) == (0, 0) else f" {when:%-I:%M %p}"
        out.append(f"{title} (due {day}{time})")
    return out


def fetch_canvas(url: str, now: datetime) -> list[str]:
    if not url:
        return []
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return canvas_tasks(response.read().decode("utf-8", "replace"), now)
    except OSError:
        return ["Couldn't reach the Canvas calendar feed (check CANVAS_ICS_URL)"]


# ---------------------------------------------------------------- emails to answer

# Senders that never need a reply.
_AUTOMATED = re.compile(
    r"no-?reply|do-?not-?reply|donotreply|notifications?|mailer|alerts?|digest|newsletter|news@|updates?@|"
    r"support@|info@|hello@|team@|careers?@|jobs@|talent|recruiting@|myworkday|greenhouse|lever\.co|ashby|"
    r"icims|tsenta|calendar|canvas|instructure|linkedin|github|google\.com|accounts\.|wordpress|otp\.|iam\.",
    re.IGNORECASE,
)
# Codes and sign-in checks: something to use, not to answer.
_CODE_SUBJECT = re.compile(r"verif|security code|one-time|otp\b|confirm your (?:email|identity)|password",
                           re.IGNORECASE)
ANSWER_QUERY = ("in:inbox newer_than:7d to:me -from:me "
                "-category:promotions -category:social -category:forums -category:updates")


def needs_reply(messages: list[dict], me: str) -> dict | None:
    """The last message of a thread if someone else wrote it and a person (not a system) sent it."""
    if not messages:
        return None
    last = messages[-1]
    address = parseaddr(last["from"])[1].lower()
    if address == me.lower() or last.get("auto") or last.get("bulk") or _AUTOMATED.search(last["from"]) \
            or _CODE_SUBJECT.search(last.get("subject", "")):
        return None
    return last


def emails_to_answer(gmails, today: date) -> list[str]:
    from googleapiclient.errors import HttpError

    people: dict[tuple[str, str], list[dict]] = {}  # (inbox, sender address) -> their unanswered emails
    for gmail in gmails:
        try:
            threads = {m["threadId"] for m in gmail.search_messages(ANSWER_QUERY, limit=60)}
            for thread_id in threads:
                last = needs_reply(gmail.thread(thread_id), gmail.address)
                if last:
                    people.setdefault((gmail.address, parseaddr(last["from"])[1].lower()), []).append(last)
        except HttpError:
            continue
    out = []
    for (inbox, _), emails in people.items():
        emails.sort(key=lambda m: m["date"])
        oldest, newest = emails[0], emails[-1]
        name = parseaddr(newest["from"])[0] or parseaddr(newest["from"])[1]
        waited = (today - date.fromisoformat(oldest["date"])).days
        ago = "since today" if waited == 0 else f"waiting {waited} day{'s' if waited > 1 else ''}"
        what = newest["subject"] or "(no subject)"
        count = f"{len(emails)} emails, latest: " if len(emails) > 1 else ""
        where = "" if len(gmails) == 1 else f" [{inbox.split('@')[0]}]"
        out.append((oldest["date"], f"{name}: {count}{what} ({ago}){where}"))
    return [line for _, line in sorted(out)]


# ---------------------------------------------------------------- stock app

_ACTION = re.compile(r"^(?:BUY|SELL|TRIM|SELL HALF|TOP UP)\b|\bGTT\b", re.IGNORECASE)


def stock_actions(folder: str, now: datetime) -> list[str]:
    """Today's buy/sell alerts and queued orders from the stock app's paper portfolios ("FYI" lines left out)."""
    if not folder:
        return []
    out = []
    for path in sorted(Path(folder).glob("paper/*.json")):
        if path.stem.startswith("account_"):
            continue
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        label = path.stem.replace("multifactor", "Multi-factor").replace("momentum", "Momentum")
        for when, text in state.get("log", []):
            if str(when).startswith(f"{now:%Y-%m-%d}") and _ACTION.search(text):
                out.append(f"{label}: {text.split(':')[0] if len(text) > 110 else text}")
        for order in state.get("pending", []):
            name = order.get("info", {}).get("name") or order.get("ticker", "")
            out.append(f"{label}: {order.get('side', '').upper()} {name} at the next open")
    return out


def load_gmails():
    """Gmail clients for every account FRIDAY reads, without opening a browser."""
    from .config import Config
    from .gmail_client import GmailClient
    from .google_auth import LoginNeeded, get_credentials

    gmails = []
    for _, token_file, credentials_file in Config.load().accounts():
        try:
            gmails.append(GmailClient(get_credentials(credentials_file, token_file, interactive=False)))
        except LoginNeeded:
            continue
    return gmails


def extra_sections(now: datetime) -> list[tuple[str, list[str]]]:
    """Every extra reminder section, in the order they're shown."""
    sections = [("Canvas due this week", fetch_canvas(os.environ.get("CANVAS_ICS_URL", "").strip(), now))]
    try:
        sections.append(("Emails waiting on your reply", emails_to_answer(load_gmails(), now.date())))
    except Exception as e:  # noqa: BLE001 - a Gmail hiccup must not stop the reminder
        sections.append(("Emails waiting on your reply", [f"Couldn't check email: {type(e).__name__}"]))
    sections.append(("Stock app", stock_actions(os.environ.get("STOCKS_DIR", "").strip(), now)))
    return sections
