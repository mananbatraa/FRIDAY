"""Sample data for trying the dashboard without a Gmail login.

    streamlit run dashboard.py -- --demo

Writes applications.csv, emails.csv, todos.csv and outreach.csv into a folder, with dates
relative to today so the "Next 48 hours" tile always has something in it.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

from .outreach import FOLLOW_UP_DUE, FOLLOWED_UP, NO_REPLY, REPLIED, WAITING
from .storage import APP_COLUMNS, EMAIL_COLUMNS, OUTREACH_COLUMNS, TODO_COLUMNS, CsvTable

TITLE = "Current Search: Q4 Senior IC & Lead Roles"

# (company, role, status, applied days ago, last update days ago, work mode, next action, notes)
_APPS = [
    ("Stripe", "Staff Software Engineer, Payments", "Interview", 24, 1, "Hybrid",
     "Send thank-you note to Sarah", "Final loop booked. Sarah Chen is the hiring manager."),
    ("Linear", "Senior Product Engineer", "Interview", 19, 2, "Remote",
     "", "Small team, async culture. Liked the take-home brief."),
    ("Figma", "Engineering Lead, Editor", "Assessment", 15, 3, "Hybrid",
     "Finish the systems take-home by Friday", "Take-home is a collaborative cursor service."),
    ("Ramp", "Senior Backend Engineer", "Interview", 21, 4, "Onsite",
     "Pick an interview slot", ""),
    ("Datadog", "Staff Engineer, Observability", "Offer", 34, 2, "Hybrid",
     "Reply to offer by Oct 27", "Verbal offer. Ask about refresh grants."),
    ("Notion", "Senior Software Engineer, AI", "Assessment", 12, 5, "Hybrid",
     "Book the CodeSignal assessment", ""),
    ("Vercel", "Senior Engineer, Edge Runtime", "Applied", 9, 9, "Remote", "", ""),
    ("Plaid", "Lead Engineer, Platform", "Applied", 8, 8, "Hybrid", "", ""),
    ("Retool", "Senior Software Engineer", "Applied", 7, 7, "Onsite", "", ""),
    ("Airtable", "Staff Engineer, Data", "Applied", 6, 6, "Remote", "", ""),
    ("Webflow", "Senior Frontend Engineer", "Applied", 5, 5, "Remote", "", ""),
    ("Asana", "Engineering Manager, Core", "Applied", 4, 4, "Hybrid", "", ""),
    ("Brex", "Senior Software Engineer, Cards", "Applied", 3, 3, "Hybrid", "", ""),
    ("Gusto", "Staff Engineer, Payroll", "Applied", 3, 3, "Onsite", "", ""),
    ("Discord", "Senior Engineer, Infrastructure", "Applied", 2, 2, "Remote", "", ""),
    ("Duolingo", "Senior Software Engineer", "Applied", 1, 1, "Onsite", "", ""),
    ("Airbnb", "Senior Software Engineer, Search", "Rejected", 30, 11, "Hybrid", "", "Role filled internally."),
    ("Dropbox", "Staff Engineer", "Rejected", 28, 13, "Remote", "", ""),
    ("Lyft", "Senior Engineer, Mapping", "Rejected", 26, 9, "Hybrid", "", ""),
    ("Coinbase", "Lead Engineer", "Rejected", 22, 6, "Remote", "", ""),
]


# (name, email, status, sent days ago, replied days ago)
_OUTREACH = [
    ("Maya Patel", "maya.patel@stripe.com", REPLIED, 12, 9),
    ("Jordan Lee", "jordan@linear.app", REPLIED, 10, 8),
    ("Priya Raman", "priya.raman@ramp.com", FOLLOW_UP_DUE, 9, None),
    ("Tom Becker", "tom.becker@datadog.com", FOLLOW_UP_DUE, 8, None),
    ("Ana Souza", "ana.souza@figma.com", FOLLOWED_UP, 16, None),
    ("Chris Wong", "chris.wong@notion.so", NO_REPLY, 24, None),
    ("Leah Kim", "leah.kim@vercel.com", WAITING, 3, None),
    ("Sam Ortiz", "sam.ortiz@plaid.com", WAITING, 2, None),
    ("Nina Shah", "nina.shah@airtable.com", WAITING, 1, None),
    ("Omar Haddad", "omar.haddad@brex.com", REPLIED, 6, 2),
]


def _at(days: int, hour: int, minute: int = 0) -> str:
    when = datetime.combine(date.today() + timedelta(days=days), datetime.min.time())
    return when.replace(hour=hour, minute=minute).isoformat(timespec="minutes")


def _rounds() -> dict:
    return {
        "Stripe": [
            {"When": _at(-6, 11), "Round": "Hiring manager screen", "Interviewer": "Sarah Chen",
             "Meeting link": "", "Prep doc": ""},
            {"When": _at(1, 14), "Round": "Final loop: system design", "Interviewer": "Sarah Chen, Marcus Lee",
             "Meeting link": "https://meet.google.com/", "Prep doc": "https://docs.google.com/"},
        ],
        "Linear": [
            {"When": _at(0, 16, 30), "Round": "Pairing session", "Interviewer": "Tuomas A.",
             "Meeting link": "https://zoom.us/", "Prep doc": ""},
        ],
        "Ramp": [
            {"When": _at(2, 10), "Round": "Phone screen", "Interviewer": "Priya Raman",
             "Meeting link": "https://meet.google.com/", "Prep doc": "https://docs.google.com/"},
        ],
        "Datadog": [
            {"When": _at(-9, 13), "Round": "Onsite loop", "Interviewer": "Elena Duarte",
             "Meeting link": "", "Prep doc": ""},
        ],
    }


def seed(folder: str) -> None:
    os.makedirs(folder, exist_ok=True)
    today = date.today()
    rounds = _rounds()
    apps, emails = [], []
    for i, (company, role, status, applied, updated, mode, action, notes) in enumerate(_APPS):
        link = f"https://mail.google.com/mail/u/0/#search/{company}"
        apps.append({
            "Company": company, "Role": role, "Status": status,
            "Applied on": (today - timedelta(days=applied)).isoformat(),
            "Last update": (today - timedelta(days=updated)).isoformat(),
            "Next action": action, "Latest email": link, "Notes": notes,
            "Work mode": mode, "Rounds": json.dumps(rounds.get(company, [])) if company in rounds else "",
        })
        sender = f"careers@{company.lower()}.com"
        emails.append({"Date": (today - timedelta(days=applied)).isoformat(), "Kind": "Applied",
                       "Company": company, "Role": role, "From": sender,
                       "Subject": f"Thanks for applying to {company}", "Email link": link, "Message ID": f"a{i}"})
        if status != "Applied":
            subject = {
                "Assessment": f"Next step: your {company} assessment",
                "Interview": f"Let's schedule your {company} interview",
                "Offer": f"Your offer from {company}",
                "Rejected": f"Update on your {company} application",
            }[status]
            emails.append({"Date": (today - timedelta(days=updated)).isoformat(), "Kind": status,
                           "Company": company, "Role": role, "From": sender, "Subject": subject,
                           "Email link": link, "Message ID": f"b{i}"})
    todos = [
        {"Task": "Review system design prep by Thursday", "Company": "Stripe",
         "Due": (today + timedelta(days=2)).isoformat(), "Done": "", "Source": "you"},
        {"Task": "Ask Maya for a referral", "Company": "Vercel",
         "Due": (today + timedelta(days=3)).isoformat(), "Done": "", "Source": "you"},
        {"Task": "Update resume with the Q3 launch", "Company": "",
         "Due": "", "Done": today.isoformat(), "Source": "you"},
    ]
    outreach = []
    for i, (name, address, status, sent, replied) in enumerate(_OUTREACH):
        company = address.split("@")[1].split(".")[0].capitalize()
        due = today - timedelta(days=sent - 7)
        outreach.append({
            "Sent on": (today - timedelta(days=sent)).isoformat(), "Name": name, "Email": address,
            "Company": company, "Subject": "Seeking your guidance", "Status": status,
            "Last reply": (today - timedelta(days=replied)).isoformat() if replied is not None else "",
            "Follow up on": due.isoformat() if status in (WAITING, FOLLOW_UP_DUE) else "",
            "Email link": f"https://mail.google.com/mail/u/0/#search/{address}",
            "Thread ID": f"t{i}", "Message ID": f"o{i}", "Notes": "",
        })
    CsvTable(os.path.join(folder, "applications.csv"), APP_COLUMNS).save(apps)
    CsvTable(os.path.join(folder, "outreach.csv"), OUTREACH_COLUMNS).save(outreach)
    CsvTable(os.path.join(folder, "emails.csv"), EMAIL_COLUMNS).save(emails)
    CsvTable(os.path.join(folder, "todos.csv"), TODO_COLUMNS).save(todos)
