"""Read job emails from Gmail and keep the application tracker up to date.

    python -m tracker.main              # update the Sheet (or the CSV files)
    python -m tracker.main --dry-run    # print what it found without saving
    python -m tracker.main --days 7     # only look at the last 7 days
    python -m tracker.main --sort-old   # also sort emails read on earlier runs (folders, old codes binned)
"""
from __future__ import annotations

import argparse
import sys
import warnings
from collections import Counter
from datetime import date, datetime, timezone

# Google's libraries warn loudly about Python 3.9 and macOS's LibreSSL; harmless here.
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

from . import llm
from .config import Config
from .folders import CODE_KEEP, by_folder, recent_codes
from .job_emails import DEFAULT_QUERY, VERIFICATION
from .models import normalize_company


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, help="how many days back to search (default 30, or DAYS in .env)")
    parser.add_argument("--query", help="custom Gmail search query")
    parser.add_argument("--dry-run", action="store_true", help="print changes without saving them")
    parser.add_argument("--limit", type=int, default=1000, help="max emails to read per run")
    parser.add_argument("--rebuild", action="store_true",
                        help="forget what was read before and re-read every email (keeps your Notes)")
    parser.add_argument("--background", action="store_true",
                        help="for scheduled runs: never open a browser, show a Mac notification for changes")
    parser.add_argument("--no-claude", action="store_true", help="use the built-in rules even if a Claude key is set")
    parser.add_argument("--sort-old", action="store_true",
                        help="also sort job emails read on earlier runs: move them into the USA Jobs folders "
                             "and bin old security-code emails")
    args = parser.parse_args(argv)

    from .gmail_client import GmailClient
    from .google_auth import LoginNeeded, get_credentials
    from .notify import notify
    from .storage import open_tables
    from .tracker import apply_email

    config = Config.load()
    query = args.query or (DEFAULT_QUERY.format(days=args.days) if args.days else config.job_query)
    try:
        creds = get_credentials(config.credentials_file, config.token_file, interactive=not args.background)
    except LoginNeeded as e:
        print(e)
        notify("FRIDAY needs you", str(e))
        return 1
    gmail = GmailClient(creds)
    app_table, email_table = open_tables(creds, config.sheet_id)
    apps, logged = app_table.load(), email_table.load()
    notes = {}
    if args.rebuild:
        notes = {(normalize_company(r.get("Company", "")), r.get("Role", "").lower()): r.get("Notes", "")
                 for r in apps if r.get("Notes")}
        apps, logged = [], []
        print("Rebuilding from scratch: re-reading every matching email")
    seen = {r.get("Message ID") for r in logged}
    first_new = len(logged)

    reader = None
    if not args.no_claude and llm.available():
        reader = llm.Claude(config.claude_model)
        print(f"Reading emails with Claude ({config.claude_model})")
    else:
        print("Reading emails with built-in rules (set ANTHROPIC_API_KEY to use Claude)")

    ids = gmail.search(query, limit=args.limit)
    new_ids = [i for i in ids if i not in seen]
    print(f"{len(ids)} emails match the search, {len(new_ids)} not seen before")

    # Oldest first, so statuses move forward in the order things happened.
    emails = []
    for n, message_id in enumerate(new_ids, 1):
        emails.append(gmail.get(message_id))
        if n % 20 == 0 or n == len(new_ids):
            print(f"  downloaded {n}/{len(new_ids)}", flush=True)
    emails.sort(key=lambda e: e.date)
    kinds, changes, needs_you, unknown = Counter(), [], [], []
    for email in emails:
        info = (reader.read(email) if reader else None) or llm.rules(email)
        kinds[info["kind"]] += 1
        logged.append({
            "Date": email.date, "Kind": info["kind"], "Company": info["company"], "Role": info["role"],
            "From": email.sender, "Subject": email.subject, "Email link": email.gmail_link, "Message ID": email.id,
        })
        if info["kind"] == VERIFICATION:
            needs_you.append(email)
            continue
        change = apply_email(apps, email, info)
        if change:
            changes.append(change)
        elif info["kind"] != "Other" and not info["company"]:
            unknown.append(email)

    for row in apps:
        row["Notes"] = row.get("Notes") or notes.get((normalize_company(row["Company"]), row["Role"].lower()), "")

    print("\n".join(f"  {c}" for c in changes) or "  no changes")
    print("By kind: " + ", ".join(f"{k} {n}" for k, n in kinds.most_common()))
    if needs_you:
        print(f"\n{len(needs_you)} verification / security-code emails (binned once they're 2 hours old):")
        for e in needs_you[-10:]:
            print(f"  ? {e.date}  {e.subject}")
    if unknown:
        print(f"\n{len(unknown)} job emails where the company couldn't be found (see the Emails tab):")
        for e in unknown[-10:]:
            print(f"  ? {e.date}  {e.sender}  |  {e.subject}")

    if args.background and changes:
        notify(f"FRIDAY: {len(changes)} update{'s' if len(changes) != 1 else ''}",
               "; ".join(c[2:] for c in changes[:3]) + (" …" if len(changes) > 3 else ""))

    folders = by_folder(logged if args.sort_old else logged[first_new:])
    codes = old_codes(gmail, recent_codes(logged, date.today(), everything=args.sort_old))
    if args.dry_run:
        for folder, ids in folders.items():
            print(f"Would move {len(ids)} emails to {folder}")
        print(f"Would bin {len(codes)} security-code emails")
        print("\nDry run: nothing saved.")
        return 0
    app_table.save(apps)
    email_table.save(logged)
    where = "Google Sheet" if config.sheet_id else "applications.csv and emails.csv"
    print(f"\nSaved {len(apps)} applications to {where}")
    move_to_folders(gmail, folders, codes)
    return 0


def old_codes(gmail, message_ids: list[str]) -> list[str]:
    """The security-code emails that arrived more than CODE_KEEP ago and aren't binned yet."""
    cutoff = datetime.now(timezone.utc) - CODE_KEEP
    old = []
    for message_id in message_ids:
        received, in_trash = gmail.arrival(message_id)
        if received <= cutoff and not in_trash:
            old.append(message_id)
    return old


def move_to_folders(gmail, folders: dict[str, list[str]], codes: list[str]) -> None:
    from googleapiclient.errors import HttpError

    try:
        for folder in folders:
            gmail.move(folders[folder], gmail.label_id(folder))
            print(f"Moved {len(folders[folder])} emails to {folder}")
        if codes:
            gmail.trash(codes)
            print(f"Binned {len(codes)} security-code emails more than 2 hours old")
    except HttpError as e:
        print(f"Couldn't sort emails in Gmail: {e}")


if __name__ == "__main__":
    sys.exit(main())
