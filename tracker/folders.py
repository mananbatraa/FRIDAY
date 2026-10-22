"""Which Gmail folder (label) each kind of job email is moved into."""
from __future__ import annotations

from datetime import date, timedelta

from .job_emails import ASSESSMENT, CONFIRMATION, INTERVIEW, OFFER, REJECTED, VERIFICATION

JOBS_FOLDER = "USA Jobs"
# Nested, so Gmail shows it inside USA Jobs.
ACTIONS_FOLDER = f"{JOBS_FOLDER}/Actions to be Taken"

# Other emails stay where they are; security-code emails go to the trash (see old_codes).
FOLDERS = {
    CONFIRMATION: JOBS_FOLDER,
    REJECTED: JOBS_FOLDER,
    ASSESSMENT: ACTIONS_FOLDER,
    INTERVIEW: ACTIONS_FOLDER,
    OFFER: ACTIONS_FOLDER,
}


def by_folder(logged: list[dict]) -> dict[str, list[str]]:
    """Group Emails-tab rows into {folder: [message IDs]}."""
    groups: dict[str, list[str]] = {}
    for row in logged:
        folder = FOLDERS.get(row.get("Kind", ""))
        if folder and row.get("Message ID"):
            groups.setdefault(folder, []).append(row["Message ID"])
    return groups


# Security codes are only needed while you fill in an application, so they're
# binned once they're a day old. Normal runs recheck the last week's, which
# catches codes that were too new on the run that first read them.
CODE_KEEP = timedelta(days=1)
CODE_RECHECK_DAYS = 7


def recent_codes(logged: list[dict], today: date, everything: bool = False) -> list[str]:
    """Message IDs of security-code emails to check for binning: the last week's, or all of them."""
    oldest = "" if everything else (today - timedelta(days=CODE_RECHECK_DAYS)).isoformat()
    return [row["Message ID"] for row in logged
            if row.get("Kind") == VERIFICATION and row.get("Message ID") and row.get("Date", "") >= oldest]
