"""Find Tenta AI confirmation emails and log each application.

    python -m tracker.main              # update the Sheet (or applications.csv)
    python -m tracker.main --dry-run    # just print what it would add
    python -m tracker.main --query 'from:tenta newer_than:7d'
"""
from __future__ import annotations

import argparse
import csv
import sys

from . import tenta_parser
from .config import Config


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--query", help="Gmail search query (overrides TENTA_QUERY)")
    parser.add_argument("--dry-run", action="store_true", help="print new applications without saving them")
    parser.add_argument("--limit", type=int, default=500, help="max emails to read per run")
    args = parser.parse_args(argv)

    from .gmail_client import GmailClient
    from .google_auth import get_credentials
    from .storage import CsvStorage, SheetStorage

    config = Config.load()
    creds = get_credentials(config.credentials_file, config.token_file)
    gmail = GmailClient(creds)
    storage = SheetStorage(creds, config.sheet_id) if config.sheet_id else CsvStorage()
    seen_ids, seen_keys = storage.known()

    query = args.query or config.tenta_query
    message_ids = gmail.search(query, limit=args.limit)
    print(f"{len(message_ids)} emails match: {query}")

    new_apps, unparsed = [], []
    for message_id in message_ids:
        if message_id in seen_ids:
            continue
        email = gmail.get(message_id)
        apps = tenta_parser.parse(email)
        if not apps:
            unparsed.append(email)
            continue
        for app in apps:
            if app.key in seen_keys:
                continue
            seen_keys.add(app.key)
            new_apps.append(app)

    for app in new_apps:
        print(f"  + {app.applied_on}  {app.company}  |  {app.job_title}")
    print(f"{len(new_apps)} new applications")

    if unparsed:
        print(f"{len(unparsed)} emails matched the search but couldn't be parsed (saved to unparsed.csv):")
        with open("unparsed.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "From", "Subject", "Email link"])
            for email in unparsed:
                writer.writerow([email.date, email.sender, email.subject, email.gmail_link])
                print(f"  ? {email.date}  {email.subject}")

    if new_apps and not args.dry_run:
        storage.append(new_apps)
        print("Saved to " + ("Google Sheet" if config.sheet_id else "applications.csv"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
