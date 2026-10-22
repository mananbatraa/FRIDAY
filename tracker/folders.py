"""Which Gmail folder (label) each kind of job email is moved into."""
from __future__ import annotations

from .job_emails import ASSESSMENT, CONFIRMATION, INTERVIEW, OFFER, REJECTED

JOBS_FOLDER = "USA Jobs"
# Nested, so Gmail shows it inside USA Jobs.
ACTIONS_FOLDER = f"{JOBS_FOLDER}/Actions to be Taken"

# Verification and Other emails stay where they are.
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
