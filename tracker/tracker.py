"""Turn classified emails into application rows and status changes."""
from __future__ import annotations

from .job_emails import ASSESSMENT, CONFIRMATION, INTERVIEW, OFFER, REJECTED
from .models import Email, normalize_company

# Later stages win; a late "thanks for applying" never pulls a row back.
# Rejected can arrive at any stage, so it always applies.
_RANK = {CONFIRMATION: 1, ASSESSMENT: 2, INTERVIEW: 3, OFFER: 4}
STATUSES = (CONFIRMATION, ASSESSMENT, INTERVIEW, OFFER, REJECTED)


def _same_role(a: str, b: str) -> bool:
    return not a or not b or a.strip().lower() == b.strip().lower()


def find_row(rows: list[dict], company: str, role: str) -> dict | None:
    key = normalize_company(company)
    matches = [r for r in rows if normalize_company(r.get("Company", "")) == key]
    exact = [r for r in matches if role and r.get("Role", "").strip().lower() == role.strip().lower()]
    if exact:
        return exact[-1]
    loose = [r for r in matches if _same_role(r.get("Role", ""), role)]
    return loose[-1] if loose else None


def apply_email(rows: list[dict], email: Email, info: dict) -> str | None:
    """Update `rows` for one email. Returns a one-line description of the change, or None."""
    kind, company, role = info["kind"], info["company"].strip(), info["role"].strip()
    if kind not in STATUSES or not company:
        return None
    link = email.gmail_link
    row = find_row(rows, company, role)
    if row is None:
        rows.append({
            "Company": company, "Role": role, "Status": kind, "Applied on": email.date,
            "Last update": email.date, "Next action": info.get("next_action", ""), "Latest email": link, "Notes": "",
        })
        return f"+ {company} | {role or '(role not found)'} | {kind}"
    if role and not row.get("Role"):
        row["Role"] = role
    old = row.get("Status", "")
    if kind == REJECTED or _RANK.get(kind, 0) > _RANK.get(old, 0):
        row["Status"] = kind
        row["Last update"] = email.date
        row["Latest email"] = link
        if info.get("next_action"):
            row["Next action"] = info["next_action"]
        if old != kind:
            return f"~ {row['Company']} | {row.get('Role') or '(role not found)'} | {old} -> {kind}"
    return None
