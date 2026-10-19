"""Pull job applications out of Tenta AI confirmation emails.

The real Tenta template hasn't been seen yet, so this tries three strategies
in order and stops at the first one that finds something:

1. Labelled fields ("Company: Acme", "Role: Data Analyst"), possibly repeated
   for emails that confirm several jobs at once.
2. Sentences like "applied to the Data Analyst role at Acme".
3. The same sentence patterns in the subject line.

Once real samples are in samples/, tighten these to the actual template.
"""
from __future__ import annotations

import re

from .models import Application, Email

_FIELD_NAMES = {
    "company": ("company", "company name", "employer", "organization", "organisation"),
    "job_title": ("job title", "position", "role", "title", "job", "job role"),
    "location": ("location", "job location", "city"),
    "job_link": ("job link", "job url", "link", "url", "job posting", "posting"),
}

_FIELD_RE = re.compile(r"^\s*[-*•]?\s*([A-Za-z][A-Za-z ]{1,24}?)\s*[:\-–]\s+(.+?)\s*$", re.MULTILINE)

_SENTENCE_RES = [
    # "applied to the Data Analyst role at Acme Corp"
    re.compile(
        r"applied (?:to|for) (?:the |a |an )?(?P<title>[^\n]+?)"
        r"(?: role| position| job| opening)? at (?P<company>[^\n.!,]+)",
        re.IGNORECASE,
    ),
    # "Your application to Acme Corp for Data Analyst"
    re.compile(
        r"application (?:to|with|at) (?P<company>[^\n.!,]+?) for (?:the )?(?P<title>[^\n.!,]+?)"
        r"(?: role| position)?(?:[.!,\n]|$)",
        re.IGNORECASE,
    ),
    # "Data Analyst at Acme Corp - application submitted"
    re.compile(
        r"^(?P<title>[^\n]+?) at (?P<company>[^\n]+?)\s*[-–|:]\s*application (?:submitted|sent)",
        re.IGNORECASE | re.MULTILINE,
    ),
]

_URL_RE = re.compile(r"https?://[^\s<>\")\]]+")
_SKIP_URL_WORDS = ("unsubscribe", "tenta", "privacy", "preferences", "facebook", "twitter", "linkedin.com/company")


def _canonical_field(label: str) -> str | None:
    label = label.strip().lower()
    for field, names in _FIELD_NAMES.items():
        if label in names:
            return field
    return None


_TRAILING_FILLER = re.compile(r"\s+(?:on your behalf|for you|today|just now|via tenta.*|through tenta.*)$", re.IGNORECASE)


def _clean(value: str) -> str:
    value = value.strip().strip("*_\"'").strip()
    return _TRAILING_FILLER.sub("", value).strip()


def _first_job_url(text: str) -> str:
    for url in _URL_RE.findall(text):
        if not any(word in url.lower() for word in _SKIP_URL_WORDS):
            return url.rstrip(".,;")
    return ""


def _from_fields(text: str) -> list[dict]:
    jobs: list[dict] = []
    current: dict = {}
    for match in _FIELD_RE.finditer(text):
        field = _canonical_field(match.group(1))
        if not field:
            continue
        # A second "Company:" means the email lists another job.
        if field in current and field == "company":
            jobs.append(current)
            current = {}
        current[field] = _clean(match.group(2))
    if current:
        jobs.append(current)
    return [job for job in jobs if job.get("company")]


def _from_sentences(text: str) -> list[dict]:
    jobs = []
    seen = set()
    for pattern in _SENTENCE_RES:
        for match in pattern.finditer(text):
            company = _clean(match.group("company"))
            title = _clean(match.group("title"))
            if (company.lower(), title.lower()) in seen:
                continue
            seen.add((company.lower(), title.lower()))
            jobs.append({"company": company, "job_title": title})
    return jobs


def parse(email: Email) -> list[Application]:
    """Return the applications this email confirms, or [] if none were found."""
    jobs = _from_fields(email.text) or _from_sentences(email.text) or _from_sentences(email.subject)
    single_link = _first_job_url(email.text) if len(jobs) == 1 else ""
    return [
        Application(
            company=job["company"],
            job_title=job.get("job_title", ""),
            location=job.get("location", ""),
            job_link=job.get("job_link") or single_link,
            applied_on=email.date,
            email_link=email.gmail_link,
            source_message_id=email.id,
        )
        for job in jobs
    ]
