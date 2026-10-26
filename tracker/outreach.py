"""Track the cold emails you send to recruiters and alumni (for example with the Mailer).

FRIDAY never sends anything. It finds the emails you already sent with a Gmail
search (OUTREACH_QUERY in .env, e.g. `in:sent subject:"Software / ML Engineer interested in"`),
logs one row per email in the Outreach table, and on every later run reads
each email's Gmail thread to see what happened:

    Waiting        sent, no answer yet
    Follow-up due  no answer after FOLLOW_UP_DAYS (default 7): time for one polite follow-up
    Followed up    you sent a follow-up in the same thread, no answer yet
    No reply       still nothing FOLLOW_UP_DAYS after your follow-up: let it go
    Replied        they wrote back (out-of-office replies don't count)
    Bounced        the address doesn't exist

Replied and Bounced are final, so marking a row Replied by hand in the
dashboard sticks.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from email.utils import parseaddr

WAITING = "Waiting"
FOLLOW_UP_DUE = "Follow-up due"
FOLLOWED_UP = "Followed up"
NO_REPLY = "No reply"
REPLIED = "Replied"
BOUNCED = "Bounced"
STATUSES = (WAITING, FOLLOW_UP_DUE, FOLLOWED_UP, NO_REPLY, REPLIED, BOUNCED)
FINAL = (REPLIED, BOUNCED)
# Worth a notification and a line in the dashboard's "Check email" summary.
NEWS = (REPLIED, BOUNCED, FOLLOW_UP_DUE)

_BOUNCE_SENDERS = re.compile(r"mailer-daemon|postmaster|mail delivery (subsystem|system)", re.IGNORECASE)
# Personal mailboxes say nothing about where someone works.
_FREE_MAIL = {"gmail", "googlemail", "outlook", "hotmail", "live", "yahoo", "icloud", "me", "aol", "proton",
              "protonmail", "zoho", "gmx", "yandex", "rediffmail"}
_DOMAIN_ENDINGS = {"com", "org", "net", "io", "co", "ai", "edu", "ac", "gov", "uk", "in", "us", "ca", "de",
                   "app", "dev", "tech", "inc", "jobs"}


def person(to_header: str) -> tuple[str, str, str]:
    """(name, address, company) of the person an email went to."""
    name, address = parseaddr(to_header)
    address = address.lower()
    local, _, domain = address.partition("@")
    if not name and re.search(r"[._-]", local):
        name = " ".join(p.capitalize() for p in re.split(r"[._-]+", local) if p and not p.isdigit())
    parts = [p for p in domain.split(".") if p]
    while len(parts) > 1 and parts[-1] in _DOMAIN_ENDINGS:
        parts.pop()
    company = ""
    if parts and parts[-1] not in _FREE_MAIL and parts[-1] not in _DOMAIN_ENDINGS:
        company = parts[-1].upper() if len(parts[-1]) <= 3 else parts[-1].capitalize()
    return name.strip().strip('"'), address, company


# The Mailer's subjects end with the company: "... Software / ML Engineer interested in Stripe".
_SUBJECT_COMPANY = re.compile(r"\binterested in (?:joining |working at )?(.+?)\s*$", re.IGNORECASE)


def new_row(message: dict) -> dict:
    name, address, company = person(message["to"])
    named = _SUBJECT_COMPANY.search(message["subject"])
    if named:
        company = named.group(1).strip(" .!")
    return {
        "Sent on": message["date"], "Name": name, "Email": address, "Company": company,
        "Subject": message["subject"], "Status": WAITING, "Last reply": "", "Follow up on": "",
        "Email link": f"https://mail.google.com/mail/u/0/#all/{message['id']}",
        "Thread ID": message["thread_id"], "Message ID": message["id"], "Notes": "",
    }


def thread_status(row: dict, messages: list[dict], today: date, follow_up_days: int) -> dict:
    """What a thread says about one outreach email: {"Status", "Last reply", "Follow up on"}."""
    ids = [m["id"] for m in messages]
    if row["Message ID"] in ids:
        later = messages[ids.index(row["Message ID"]) + 1:]
    else:  # the original was deleted; judge by date
        later = [m for m in messages if m["date"] >= row["Sent on"]]
    theirs = [m for m in later if "SENT" not in m["labels"]]
    replies = [m for m in theirs if not _BOUNCE_SENDERS.search(m["from"]) and not m["auto"]]
    if replies:
        return {"Status": REPLIED, "Last reply": replies[-1]["date"], "Follow up on": ""}
    if any(_BOUNCE_SENDERS.search(m["from"]) for m in theirs):
        return {"Status": BOUNCED, "Last reply": "", "Follow up on": ""}
    follow_ups = [m for m in later if "SENT" in m["labels"]]
    last_touch = date.fromisoformat(follow_ups[-1]["date"] if follow_ups else row["Sent on"])
    due = last_touch + timedelta(days=follow_up_days)
    if follow_ups:
        return {"Status": NO_REPLY if today >= due else FOLLOWED_UP, "Last reply": "", "Follow up on": ""}
    return {"Status": FOLLOW_UP_DUE if today >= due else WAITING, "Last reply": "", "Follow up on": due.isoformat()}


def label(row: dict) -> str:
    who = row.get("Name") or row.get("Email") or "(unknown)"
    return f"{who} ({row['Company']})" if row.get("Company") else who


def update(gmail, rows: list[dict], query: str, today: date, follow_up_days: int = 7,
           limit: int = 500) -> tuple[list[str], list[str]]:
    """Log newly sent outreach emails and refresh every row's status, in place.

    Returns (one line per newly logged email, one line per status worth telling you about).
    """
    from googleapiclient.errors import HttpError

    threads: dict[str, list[dict]] = {}

    def thread(thread_id: str) -> list[dict] | None:
        if thread_id not in threads:
            try:
                threads[thread_id] = gmail.thread(thread_id)
            except HttpError:  # deleted for good; keep the row as it is
                threads[thread_id] = None
        return threads[thread_id]

    logged = {r.get("Message ID") for r in rows} | {r.get("Thread ID") for r in rows}
    sent, new_ids = [], set()
    for match in reversed(gmail.search_messages(query, limit)):  # oldest first
        if match["id"] in logged or match["threadId"] in logged:
            continue  # already logged, or a follow-up in a logged thread
        message = next((m for m in thread(match["threadId"]) or [] if m["id"] == match["id"]), None)
        if not message or "SENT" not in message["labels"] or not message["to"]:
            continue
        row = new_row(message)
        rows.append(row)
        logged |= {row["Message ID"], row["Thread ID"]}
        new_ids.add(row["Message ID"])
        sent.append(f"> {label(row)} | {row['Subject']}")

    news = []
    for row in rows:
        old = row.get("Status", "")
        if old in FINAL or not row.get("Thread ID") or not _is_iso(row.get("Sent on", "")):
            continue
        messages = thread(row["Thread ID"])
        if messages is None:
            continue
        status = thread_status(row, messages, today, follow_up_days)
        if status["Status"] not in FINAL and row.get("Email"):
            reply = _reply_elsewhere(gmail, row, thread)
            if reply:
                status = {"Status": REPLIED, "Last reply": reply, "Follow up on": ""}
        row.update(status)
        # A first run finds older emails already due; only a reply or bounce is news for those.
        first_look = row["Message ID"] in new_ids and status["Status"] == FOLLOW_UP_DUE
        if status["Status"] != old and status["Status"] in NEWS and not first_look:
            news.append(f"~ Outreach | {label(row)} | {old or WAITING} -> {status['Status']}")
    return sent, news


def _reply_elsewhere(gmail, row: dict, thread) -> str:
    """Date of an answer from the same person in a different thread, or ""."""
    sent_on = date.fromisoformat(row["Sent on"])
    query = (f'from:{row["Email"]} after:{sent_on:%Y/%m/%d} '
             '-subject:("automatic reply" OR "out of office" OR "auto reply")')
    for match in gmail.search_messages(query, limit=5):
        if match["threadId"] == row["Thread ID"]:
            continue  # same thread: already judged, e.g. an auto-reply
        message = next((m for m in thread(match["threadId"]) or [] if m["id"] == match["id"]), None)
        if message and not message["auto"] and message["date"] >= row["Sent on"]:
            return message["date"]
    return ""


def _is_iso(day: str) -> bool:
    try:
        date.fromisoformat(day)
    except ValueError:
        return False
    return True
