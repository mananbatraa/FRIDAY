"""Read job emails from Gmail and keep the application tracker up to date.

    python -m tracker.main              # update the Sheet (or the CSV files)
    python -m tracker.main --dry-run    # print what it found without saving
    python -m tracker.main --days 7     # only look at the last 7 days
    python -m tracker.main --sort-old   # also sort emails read on earlier runs (folders, old codes binned)

With OUTREACH_QUERY set in .env it also logs the cold emails you sent and
checks them for replies (see tracker/outreach.py).
"""
from __future__ import annotations

import argparse
import re
import sys
import warnings
from collections import Counter
from datetime import date, datetime, timezone

# Google's libraries warn loudly about Python 3.9 and macOS's LibreSSL; harmless here.
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

from . import llm, outreach
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
    parser.add_argument("--no-outreach", action="store_true", help="skip checking your sent outreach emails")
    args = parser.parse_args(argv)

    from .gmail_client import GmailClient
    from .google_auth import LoginNeeded, get_credentials
    from .notify import notify
    from .storage import open_outreach_table, open_tables
    from .tracker import apply_email

    config = Config.load()
    query = args.query or (DEFAULT_QUERY.format(days=args.days) if args.days else config.job_query)
    # Every Gmail account to read. The first one also holds the Sheet, if you use one.
    gmails = []
    for address, token_file, credentials_file in config.accounts():
        try:
            creds = get_credentials(credentials_file, token_file, interactive=not args.background, account=address)
        except LoginNeeded as e:
            message = f"{address or 'Main account'}: {e}"
            print(message)
            notify("FRIDAY needs you", message)
            if not gmails and not address:
                return 1
            continue
        gmails.append(GmailClient(creds))
        if address and gmails[-1].address.lower() != address.lower():
            print(f"Warning: {token_file} is logged in as {gmails[-1].address}, not {address}")
    gmail = gmails[0]
    main_creds = gmail.creds
    app_table, email_table = open_tables(main_creds, config.sheet_id)
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

    emails = []
    for account in gmails:
        ids = account.search(query, limit=args.limit)
        new_ids = [i for i in ids if i not in seen]
        print(f"{account.address}: {len(ids)} emails match the search, {len(new_ids)} not seen before")
        for n, message_id in enumerate(new_ids, 1):
            emails.append(account.get(message_id))
            if n % 20 == 0 or n == len(new_ids):
                print(f"  downloaded {n}/{len(new_ids)}", flush=True)
    # Oldest first, so statuses move forward in the order things happened.
    emails.sort(key=lambda e: e.date)
    kinds, changes, needs_you, unknown = Counter(), [], [], []
    for email in emails:
        info = (reader.read(email) if reader else None) or llm.rules(email)
        kinds[info["kind"]] += 1
        logged.append({
            "Date": email.date, "Kind": info["kind"], "Company": info["company"], "Role": info["role"],
            "From": email.sender, "Subject": email.subject, "Email link": email.gmail_link, "Message ID": email.id,
            "Account": email.account,
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

    outreach_table = outreach_rows = None
    if config.outreach_query and not args.no_outreach:
        outreach_table = open_outreach_table(main_creds, config.sheet_id)
        outreach_rows = outreach_table.load()
        sent, news = [], []
        for account in gmails:  # a thread from the other account is simply not found, and left alone
            s_, n_ = outreach.update(account, outreach_rows, config.outreach_query, date.today(), config.follow_up_days)
            sent, news = sent + s_, news + n_
        print(f"\nOutreach: {len(sent)} sent emails logged, {len(outreach_rows)} tracked")
        for line in sent[-10:] + news:
            print(f"  {line}")
        if len(sent) > 10:
            print(f"  (and {len(sent) - 10} more sent emails)")
        changes += news

    if args.background:
        alert = phone_alert(changes)
        if alert:
            notify(*alert)

    # Each email is sorted in the mailbox it came from (rows saved before this had no Account: the main one).
    to_sort = logged if args.sort_old else logged[first_new:]
    sorting = []
    for account in gmails:
        mine = lambda rows: [r for r in rows if (r.get("Account") or gmail.address) == account.address]  # noqa: E731
        sorting.append((account, by_folder(mine(to_sort)),
                        old_codes(account, recent_codes(mine(logged), date.today(), everything=args.sort_old))))
    if args.dry_run:
        for account, folders, codes in sorting:
            for folder, ids in folders.items():
                print(f"{account.address}: would move {len(ids)} emails to {folder}")
            print(f"{account.address}: would bin {len(codes)} security-code emails")
        print("\nDry run: nothing saved.")
        return 0
    app_table.save(apps)
    email_table.save(logged)
    where = "Google Sheet" if config.sheet_id else "applications.csv and emails.csv"
    print(f"\nSaved {len(apps)} applications to {where}")
    if outreach_table:
        outreach_table.save(outreach_rows)
        print(f"Saved {len(outreach_rows)} outreach emails to " + ("the Outreach tab" if config.sheet_id else "outreach.csv"))
    for account, folders, codes in sorting:
        if len(gmails) > 1:
            print(f"{account.address}:")
        move_to_folders(account, folders, codes)
    return 0


# Changes worth interrupting you for; new applications and rejections are only counted.
_IMPORTANT = re.compile(r"\b(?:Interview|Assessment|Offer|Replied|Bounced|Follow-up due)$")


def phone_alert(changes: list[str]) -> tuple[str, str] | None:
    """(title, message) for an alert, or None when nothing needs you (e.g. only "thanks for applying" emails)."""
    important = [c[2:] for c in changes if _IMPORTANT.search(c)]
    if not important:
        return None
    applied = sum(c.endswith("| Applied") for c in changes)
    rejected = sum(c.endswith("Rejected") for c in changes)
    plural = lambda n, word: f"{n} {word}{'s' if n != 1 else ''}"  # noqa: E731
    counts = ", ".join(x for x in (plural(applied, "new application") if applied else "",
                                   plural(rejected, "rejection") if rejected else "") if x)
    message = "; ".join(important[:4]) + (f" (+{len(important) - 4} more)" if len(important) > 4 else "")
    return (f"FRIDAY: {len(important)} need{'s' if len(important) == 1 else ''} you",
            message + (f". Also {counts}." if counts else ""))


def old_codes(gmail, message_ids: list[str]) -> list[str]:
    """The security-code emails that arrived more than CODE_KEEP ago and aren't binned yet."""
    from googleapiclient.errors import HttpError

    cutoff = datetime.now(timezone.utc) - CODE_KEEP
    old = []
    for message_id in message_ids:
        try:
            received, in_trash = gmail.arrival(message_id)
        except HttpError:  # e.g. already deleted for good; it must not stop the run before saving
            continue
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
