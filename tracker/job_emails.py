"""Rules for reading job-application emails sent by companies and job sites.

Tsenta applies with your own email address, so the confirmations come straight
from each company (often through Greenhouse, Workday, Lever and similar). This
module decides what kind of email it is and who it's from, without any API.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parseaddr

from .models import Email

CONFIRMATION = "Applied"
ASSESSMENT = "Assessment"
INTERVIEW = "Interview"
OFFER = "Offer"
REJECTED = "Rejected"
VERIFICATION = "Verification"  # security codes, "confirm your identity": not a status
OTHER = "Other"

# Gmail search for anything that looks job-related. Narrowed further by classify().
DEFAULT_QUERY = (
    "newer_than:{days}d ("
    "subject:(application OR applying OR applied OR apply OR interview OR assessment OR offer "
    "OR candidate OR interest OR resume OR position OR role) "
    "OR from:(greenhouse.io OR greenhouse-mail.io OR lever.co OR myworkday.com OR myworkdayjobs.com "
    "OR ashbyhq.com OR smartrecruiters.com OR icims.com OR taleo.net OR jobvite.com OR workablemail.com "
    "OR successfactors.com OR tsenta))"
)

_KIND_PHRASES = [
    (VERIFICATION, (
        "security code", "verification code", "verify your", "confirm your identity", "confirm your email",
        "activate your account", "candidate account", "reset your password", "one-time code",
    )),
    (OFFER, ("offer letter", "pleased to offer", "extend an offer", "extend you an offer", "offer of employment")),
    (REJECTED, (
        "unfortunately", "not to move forward", "not moving forward", "will not be moving forward",
        "decided to pursue other", "other candidates", "position has been filled", "not been selected",
        "were not selected", "regret to inform", "not proceed with your application", "no longer under consideration",
    )),
    (INTERVIEW, (
        "schedule an interview", "interview invitation", "invite you to interview", "invitation to interview",
        "like to interview", "next round", "phone screen", "schedule a call", "calendly.com", "your interview",
        "interview with",
    )),
    (ASSESSMENT, (
        "online assessment", "coding challenge", "coding assessment", "hackerrank", "codesignal", "codility",
        "hirevue", "take-home", "technical assessment", "complete the assessment",
    )),
    (CONFIRMATION, (
        "thank you for applying", "thanks for applying", "thank you for your application", "received your application",
        "application received", "got your application", "application has been received", "received your resume",
        "thank you for your interest", "thanks for your interest", "submitting your application",
        "application submitted", "submitted your application", "your application for", "your application to",
        "your application with", "application to", "for applying", "your job application", "received your job application",
    )),
]


def _match_kind(text: str) -> str | None:
    text = text.lower()
    for kind, phrases in _KIND_PHRASES:
        if any(p in text for p in phrases):
            return kind
    return None


def classify(email: Email) -> str:
    subject_kind = _match_kind(email.subject)
    body_kind = _match_kind(email.text[:4000])
    if subject_kind in (VERIFICATION, OFFER, REJECTED, INTERVIEW, ASSESSMENT):
        return subject_kind
    # Rejections often reuse a friendly "Thank you for your interest" subject.
    if body_kind == REJECTED:
        return REJECTED
    if subject_kind == CONFIRMATION:
        return CONFIRMATION
    return body_kind or OTHER


# ---------------------------------------------------------------- extraction

_ROLE_WORDS = re.compile(
    r"\b(engineer|engineering|developer|analyst|intern|internship|scientist|manager|designer|specialist|associate|"
    r"fellowship|fellow|architect|consultant|programmer|sre|devops|lead|researcher|technician|administrator|"
    r"position|role|graduate|grad|trainee|apprentice|careers?)\b",
    re.IGNORECASE,
)
_GENERIC_SENDERS = re.compile(
    r"^(no-?reply|do-?not-?reply|donotreply|notifications?|greenhouse|workday|lever|ashby|smartrecruiters|icims|"
    r"taleo|jobvite|workable|tsenta.*|human resources|hr|recruiting|careers?|talent( acquisition)?|hiring( team)?|"
    r"jobs?|team|.*\.sender|workdaysystem.*)$",
    re.IGNORECASE,
)
_GENERIC_DOMAINS = (
    "gmail.com", "greenhouse.io", "greenhouse-mail.io", "lever.co", "myworkday.com", "myworkdayjobs.com",
    "ashbyhq.com", "smartrecruiters.com", "icims.com", "taleo.net", "jobvite.com", "workablemail.com",
    "successfactors.com", "tsenta", "applytojob.com", "bamboohr.com", "recruitee.com", "breezy.hr", "paylocity.com",
    "ultipro.com", "oraclecloud.com", "eightfold.ai", "phenom", "avature", "jazzhr", "dayforce",
)
_SENDER_NOISE = re.compile(
    r"\b(hiring team|hiring|recruiting team|recruiting|recruitment|talent acquisition|talent team|talent|careers?|"
    r"jobs at|jobs|human resources|hr|people team|team|inbox|no-?reply|donotreply|do not reply)\b",
    re.IGNORECASE,
)

_COMPANY_PATTERNS = [
    # "... at Affirm"
    r"\b(?i:role|position|job|opening|internship|opportunity|engineer\w*|developer|analyst|intern|team|\))\s+(?i:at|with)\s+(?P<c>[A-Z0-9][\w&.,'’ -]{1,60}?)(?=\s*(?:[!?.:;|(]|\s[-–—]\s|,\s|\bfor\b|\band\b|$))",
    r"\b(?i:at)\s+(?P<c>[A-Z0-9][\w&.'’ -]{1,60}?)(?=\s*(?:[!?.;|]|\s[-–—]\s|$))",
    # "interest in (joining) Citi!"
    r"(?i:interest in (?:joining |working (?:at|with|for) )?)(?!(?i:the|our|a|an|this)\b)(?P<c>[A-Z0-9][\w&.'’ -]{1,60}?)(?=\s*(?:[!?.;,|]|\s(?:and|for|as)\b|$))",
    # "applying to Aurora", "Application With ZEFR", "Applying to Ensign Services"
    r"(?i:(?:applying|applied|application|apply)\s+(?:to|with|at)\s+(?:the\s+)?)(?P<c>[A-Z0-9][\w&.,'’() -]{1,70}?)(?=\s*(?:[!?.;|]|\s[-–—]\s|,\s|\bfor\b|$))",
    # lowercase-first names like "eClerx": "Application with eClerx"
    r"(?i:(?:applying|applied|application|apply)\s+(?:to|with|at)\s+)(?!(?i:the|our|a|an|this|your|us)\b)(?P<c>[a-z][A-Z][\w&.'’ -]{1,60}?)(?=\s*(?:[!?.;|]|\s[-–—]\s|$))",
    # "you're interested in Levanta and our mission"
    r"(?i:interested in (?:joining |working (?:at|with|for) )?)(?!(?i:the|our|a|an|this|being)\b)(?P<c>[A-Z0-9][\w&.'’ -]{1,60}?)(?=\s*(?:[!?.;,|]|\s(?:and|for|as)\b|$))",
    # "joining TicketManager"
    r"\b(?i:join(?:ing)?\s+(?:the\s+)?)(?!(?i:our|us|the team)\b)(?P<c>[A-Z0-9][\w&.'’ -]{1,60}?)(?=\s*(?:[!?.;,|]|\s(?:team|and|as)\b|$))",
    # "Application Received – NTT DATA AIVista"
    r"(?i:application received|received your application)\s*[-–—:|]\s*(?P<c>[A-Z0-9][^!?.|\n]{1,60})",
    # "We've received your application! | Abby Care"
    r"\|\s*(?P<c>[A-Z0-9][^|\n]{1,60})\s*$",
    # "Leidos -Thank You For Applying ..."
    r"^(?P<c>[A-Z0-9][\w&.'’ ]{1,40}?)\s*[-–—:]\s*(?i:thank)",
]

_ROLE_PATTERNS = [
    r"(?:application|applying|applied)\s+(?:for|to)\s+(?:the\s+|our\s+)?(?P<r>[^!?\n]{3,90}?)\s+(?:role|position|job|opportunity)?\s*(?:at|with)\s+[A-Z]",
    r"(?:for|in|to)\s+(?:the|our)\s+(?P<r>[^!?\n]{3,90}?)\s+(?:role|position|opportunity|job|internship|opening)\b",
    r"(?:position|role) of\s+(?P<r>[^!?.,\n]{3,90})",
    r"(?:applying|applied)\s+(?:for|to)\s+(?:the\s+)?(?P<r>[^!?\n]{3,90}?)\s+[-–]\s+\d{4,}",
    r"(?:received your (?:job )?application|application) for\s+(?:the\s+|our\s+)?(?P<r>[^!?\n]{3,90}?)(?:\s+(?:role|position|opportunity))?(?:\s+at\s|[!.]|\s+[-–]\s|$)",
    r"(?:applying|applied) to\s+(?:the\s+|our\s+)?(?P<r>[^!?\n]{3,90}?)\s+(?:role|position)\b",
    r"(?:applying|applied) to\s+(?:the\s+)?(?P<r>[^!?\n]{3,90}?)(?=\s*$)",
]


@dataclass
class Extracted:
    company: str
    role: str


def _clean(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" \t-–—:|,.!?\"'*")
    value = re.sub(r"^(?:the|our)\s+", "", value, flags=re.IGNORECASE)
    return value.strip()


def _looks_like_role(text: str) -> bool:
    return bool(_ROLE_WORDS.search(text)) or bool(re.search(r"\b\d{5,}\b", text))


def _company_from_text(text: str) -> str:
    for pattern in _COMPANY_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.MULTILINE):
            candidate = _clean(match.group("c"))
            if not candidate or len(candidate) > 60 or _looks_like_role(candidate):
                continue
            if candidate.lower() in {"you", "us", "our team", "manan", "this", "it", "the team"}:
                continue
            return candidate
    return ""


def _company_from_sender(sender: str) -> str:
    name, address = parseaddr(sender)
    name = re.sub(r"^.{1,30}?\s+from\s+", "", name, flags=re.IGNORECASE)  # "Miles from Avis Budget"
    name = re.sub(r"^(?:donotreply|do-?not-?reply|no-?reply)[_ -]+|[_ -]+(?:hr|careers|jobs)$", "", name, flags=re.IGNORECASE)
    cleaned = _clean(_SENDER_NOISE.sub("", name.replace("’s", "").replace("'s", "")))
    cleaned = re.sub(r"[,.]+$", "", cleaned).strip()
    if name and not _GENERIC_SENDERS.match(name.strip()) and len(cleaned) >= 2:
        return cleaned.title() if cleaned.islower() else cleaned
    domain = address.rsplit("@", 1)[-1].lower() if "@" in address else ""
    if domain and not any(g in domain for g in _GENERIC_DOMAINS):
        parts = [p for p in domain.split(".") if p not in {"mail", "email", "careers", "jobs", "hr", "talent", "us", "com",
                                                          "co", "io", "ai", "net", "org", "in", "uk"}]
        if parts:
            return parts[-1].capitalize()
    return ""


def _role_from_text(text: str) -> str:
    for pattern in _ROLE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            role = _clean(match.group("r"))
            if role and _looks_like_role(role) and len(role) <= 90:
                return role
    return ""


def extract(email: Email) -> Extracted:
    first_lines = "\n".join(email.text.splitlines()[:15])[:1500]
    company = _company_from_text(email.subject) or _company_from_text(first_lines) or _company_from_sender(email.sender)
    role = _role_from_text(email.subject) or _role_from_text(first_lines)
    return Extracted(company=company, role=role)
