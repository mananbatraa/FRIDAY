"""The only actions FRIDAY's phone assistant (tracker/agent.py) can take.

    python -m tracker.tools ask "list"              a FRIDAY command: list, pending, done, undo, todo
    python -m tracker.tools contacts dipesh         addresses matching a name, most emailed first, per account
    python -m tracker.tools emails "from:josh"      recent emails matching a Gmail search, with ids to reply to
    python -m tracker.tools applications nvidia     your job applications matching a company (or "all")
    python -m tracker.tools draft --to a@b.com --subject S --body B [--cc ..] [--account gmail]
                                                    save a draft; you send it by texting "send <code>"
    python -m tracker.tools draft --reply-to school:18f2... --body B
                                                    a reply in that email's thread, to its sender
    ... draft ... --replaces 1956                   and delete the draft it replaces
    python -m tracker.tools apply https://...       open a job posting in Chrome for Tsenta to apply

Nothing here sends an email: only your own "send <code>" text does (tracker/inbox.py).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText

PENDING_FILE = "logs/pending_sends.json"  # drafts waiting for "send <code>"
PENDING_FOR = timedelta(days=1)


def _accounts() -> dict[str, tuple[str, str]]:
    """{"gmail" or "school": (login file, app file)} for the Gmail accounts FRIDAY reads (school: a .edu address)."""
    from .config import Config

    found = {}
    for address, token, creds in Config.load().accounts():
        found["school" if address.endswith(".edu") else "gmail"] = (token, creds)
    return found


def _service(account: str):
    from googleapiclient.discovery import build

    from .google_auth import get_credentials

    token, creds = _accounts()[account]
    return build("gmail", "v1", credentials=get_credentials(creds, token, interactive=False), cache_discovery=False)


def _headers(service, message_id: str, names: list[str]) -> dict:
    message = service.users().messages().get(userId="me", id=message_id, format="metadata",
                                             metadataHeaders=names).execute()
    found = {h["name"]: h["value"] for h in message["payload"]["headers"]}
    found["snippet"] = message.get("snippet", "")
    return found


def contacts(name: str) -> list[str]:
    """Addresses in From, To or Cc of recent emails whose name or address contains `name`,
    most emailed first, each with the account it turned up in."""
    found: dict[str, list] = {}  # address -> [person, count, accounts]
    for account in _accounts():
        service = _service(account)
        query = f"from:{name} OR to:{name} OR cc:{name}"
        for m in service.users().messages().list(userId="me", q=query, maxResults=25).execute().get("messages", []):
            h = _headers(service, m["id"], ["From", "To", "Cc"])
            for person in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", ", ".join(h.get(k, "") for k in ("From", "To", "Cc"))):
                person = person.strip()
                match = re.search(r"<?([\w.+-]+@[\w-]+\.[\w.-]+)>?", person)
                if match and name.lower() in person.lower():
                    entry = found.setdefault(match.group(1).lower(), [person, 0, set()])
                    entry[1] += 1
                    entry[2].add(account)
    ranked = sorted(found.values(), key=lambda e: -e[1])
    return [f"{person} ({count} email{'s' if count != 1 else ''}, in your {'/'.join(sorted(accounts))} account)"
            for person, count, accounts in ranked[:8]]


def emails(query: str) -> list[str]:
    lines = []
    for account in _accounts():
        service = _service(account)
        for m in service.users().messages().list(userId="me", q=query, maxResults=5).execute().get("messages", []):
            h = _headers(service, m["id"], ["From", "Subject", "Date"])
            lines.append(f"id {account}:{m['id']} | {h.get('Date', '')[:16]} | {h.get('From', '')} | "
                         f"{h.get('Subject', '')}\n    {h['snippet'][:200]}")
    return lines


def draft(to: str, subject: str, body: str, cc: str = "", account: str = "",
          reply_to: str = "", replaces: str = "") -> str:
    """Save a Gmail draft and the code you text to send it.

    reply_to ("school:<message id>" from `emails`) makes it a reply in that thread, to its sender unless
    `to` says otherwise. replaces deletes the earlier draft with that code (a revision of it).
    """
    thread, answering = None, ""
    if reply_to:
        account, _, message_id = reply_to.partition(":")
        if account not in _accounts() or not message_id:
            return "reply-to must be an id from the emails command, like school:18f2a..."
        original = _service(account).users().messages().get(
            userId="me", id=message_id, format="metadata",
            metadataHeaders=["From", "Reply-To", "Subject", "Message-ID", "References", "Date"]).execute()
        h = {x["name"].lower(): x["value"] for x in original["payload"]["headers"]}
        thread = original["threadId"]
        to = to or h.get("reply-to") or h.get("from", "")
        subject = subject or h.get("subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        answering = f" It replies to {h.get('from', '')}'s email of {h.get('date', '')[:16]}: \"{original.get('snippet', '')[:120]}\""
    account = account or ("school" if "school" in _accounts() else "gmail")
    if not to or not subject:
        return "A new email needs --to and --subject."
    message = MIMEText(body, "plain", "utf-8")
    message["To"], message["Subject"] = to, subject
    if cc:
        message["Cc"] = cc
    if reply_to:
        message["In-Reply-To"] = h.get("message-id", "")
        message["References"] = f"{h.get('references', '')} {h.get('message-id', '')}".strip()
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body_json = {"message": {"raw": raw, **({"threadId": thread} if thread else {})}}
    saved = _service(account).users().drafts().create(userId="me", body=body_json).execute()
    replaced = ""
    if replaces:
        replaced = " " + cancel(replaces).replace("Nothing was sent.", "(replaced; nothing was sent)")
    pending = load_pending()
    code = f"{secrets.randbelow(9000) + 1000}"
    while code in pending:
        code = f"{secrets.randbelow(9000) + 1000}"
    pending[code] = {"account": account, "draft": saved["id"], "to": to, "cc": cc, "subject": subject,
                     "saved": datetime.now().isoformat(timespec="minutes")}
    _save_pending(pending)
    return (f"Draft saved in the {account} account to {to}" + (f", cc {cc}" if cc else "") +
            f", subject \"{subject}\", code {code}. Not sent.{answering}{replaced} Tell the user to text "
            f"\"send {code}\" to send it or \"cancel {code}\" to delete it.")


def applications(company: str) -> list[str]:
    """Rows of your job tracker whose company matches (or every active one for "all")."""
    from .reminder import load_rows

    apps, _, _ = load_rows()
    if company.lower() != "all":
        apps = [a for a in apps if company.lower() in a.get("Company", "").lower()]
    else:
        apps = [a for a in apps if a.get("Status", "") not in ("Rejected", "Withdrawn")]
    apps.sort(key=lambda a: a.get("Last update", ""), reverse=True)
    return [f"{a.get('Company')} | {a.get('Role')} | {a.get('Status')} | applied {a.get('Applied on') or '?'} | "
            f"last update {a.get('Last update') or '?'}" + (f" | next: {a['Next action']}" if a.get("Next action") else "")
            for a in apps[:15]]


def load_pending() -> dict:
    try:
        with open(PENDING_FILE, encoding="utf-8") as f:
            pending = json.load(f)
    except (OSError, ValueError):
        return {}
    cutoff = (datetime.now() - PENDING_FOR).isoformat()
    return {code: p for code, p in pending.items() if p["saved"] >= cutoff}


def _save_pending(pending: dict) -> None:
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, indent=1)


def send(code: str) -> str:
    """Send the draft saved under `code`. Only your own "send <code>" text calls this."""
    pending = load_pending()
    p = pending.pop(code.strip(), None)
    if not p:
        return f"No draft waiting with code {code!r}. Codes last a day."
    _service(p["account"]).users().drafts().send(userId="me", body={"id": p["draft"]}).execute()
    _save_pending(pending)
    return f"Sent \"{p['subject']}\" to {p['to']}" + (f", cc {p['cc']}" if p["cc"] else "") + "."


def cancel(code: str) -> str:
    pending = load_pending()
    p = pending.pop(code.strip(), None)
    if not p:
        return f"No draft waiting with code {code!r}."
    _service(p["account"]).users().drafts().delete(userId="me", id=p["draft"]).execute()
    _save_pending(pending)
    return f"Deleted the draft \"{p['subject']}\". Nothing was sent."


def apply(url: str) -> str:
    """Open a job posting in Chrome, where the Tsenta extension applies, and log it like the job opener does."""
    from .open_jobs import LOG_FILE, Job, log_opened, open_tab

    if not re.match(r"https?://[^\s]+$", url):
        return "That isn't a web link."
    open_tab(url, "Google Chrome")
    log_opened(LOG_FILE, [Job(company="(texted)", role="", location="", age="", url=url)])
    return "Opened in Chrome on the Mac for Tsenta to apply. Check its dashboard for anything it needs from you."


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ask", help="a FRIDAY command: list, pending, done, undo, todo").add_argument("text")
    sub.add_parser("contacts", help="email addresses matching a name").add_argument("name")
    sub.add_parser("emails", help="recent emails matching a Gmail search").add_argument("query")
    d = sub.add_parser("draft", help="save an email draft for you to send with a code")
    d.add_argument("--to", default="")
    d.add_argument("--subject", default="")
    d.add_argument("--body", required=True)
    d.add_argument("--cc", default="")
    d.add_argument("--account", choices=["school", "gmail"], default="", help="default: school if you have one")
    d.add_argument("--reply-to", default="", help="an id from the emails command, to reply in that thread")
    d.add_argument("--replaces", default="", help="the code of a draft this one replaces (it gets deleted)")
    sub.add_parser("applications", help="your job applications matching a company, or all").add_argument("company")
    sub.add_parser("apply", help="open a job posting in Chrome for Tsenta").add_argument("url")
    args = parser.parse_args(argv)

    from .config import Config
    from .google_auth import LoginNeeded

    Config.load()
    try:
        if args.command == "ask":
            from .inbox import answer, parse

            if parse(args.text)[0] not in ("list", "pending", "done", "undo", "todo"):
                print("Only list, pending, done, undo and todo can be run this way.")
                return 1
            print(answer(args.text, datetime.now()))
        elif args.command == "contacts":
            print("\n".join(contacts(args.name)) or f"No addresses found for {args.name!r}.")
        elif args.command == "emails":
            print("\n".join(emails(args.query)) or "No emails match.")
        elif args.command == "draft":
            print(draft(args.to, args.subject, args.body, args.cc, args.account, args.reply_to, args.replaces))
        elif args.command == "applications":
            print("\n".join(applications(args.company)) or f"No applications match {args.company!r}.")
        elif args.command == "apply":
            print(apply(args.url))
    except LoginNeeded as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
