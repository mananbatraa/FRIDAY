"""Rules for reading job-application emails sent by companies and job sites.

Tsenta applies with your own email address, so the confirmations come straight
from each company (often through Greenhouse, Workday, Lever and similar). This
module decides what kind of email it is and who it's from, without any API.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from email.utils import parseaddr

from .models import Email, normalize_company

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
    "OR successfactors.com OR tsenta OR greenhouse-jobs.com OR paycomonline.com) "
    "OR subject:(\"one-time password\" OR OTP OR \"verify your email\" OR \"verification code\" OR \"security code\" OR \"confirm your identity\" OR \"verify your identity\")) "
    "-category:promotions"
)

# Newsletters and marketing senders: never an application, however job-y the words.
_NEWSLETTER_SENDERS = re.compile(
    r"newsletter|beehiiv|substack|mailchimp|mcsv\.net|convertkit|kit-mail|mailerlite|sendinblue|brevo|"
    r"hubspot|klaviyo|medium\.com|webinar|masterclass|digest",
    re.IGNORECASE,
)
_MARKETING_WORDS = ("masterclass", "webinar", "unsubscribe from this newsletter", "weekly newsletter",
                    "reserve your free spot", "register now", "free workshop")

_KIND_PHRASES = [
    (VERIFICATION, (
        "security code", "verification code", "verify your", "confirm your identity", "confirm your email",
        "activate your account", "candidate account", "reset your password", "one-time code", "one-time password",
    )),
    (OFFER, ("pleased to offer you", "extend you an offer", "extend an offer to you", "offer of employment",
             "your offer letter", "attached offer letter", "congratulations on your offer")),
    (REJECTED, (
        "unfortunately", "not to move forward", "not moving forward", "will not be moving forward",
        "decided to pursue other", "other candidates", "position has been filled", "not been selected",
        "were not selected", "regret to inform", "not proceed with your application", "no longer under consideration",
    )),
    (INTERVIEW, (
        "schedule an interview", "interview invitation", "invite you to interview", "invitation to interview",
        "like to interview", "next round", "phone screen", "schedule a call", "calendly.com", "your interview is", "your interview has", "schedule your interview",
        "confirm your interview",
        "interview with", "technical interview", "invite you to the next",
        "dates and times when you", "share your availability", "your availability for",
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


def is_marketing(email: Email) -> bool:
    if "CATEGORY_PROMOTIONS" in email.labels or _NEWSLETTER_SENDERS.search(email.sender):
        return True
    text = f"{email.subject}\n{email.text[:6000]}".lower()
    return any(w in text for w in _MARKETING_WORDS)


# Codes also come from airlines, banks and GitHub; those aren't job emails.
_JOB_CONTEXT = re.compile(
    r"\b(candidates?|recruit\w*|applicants?|your application|job application|careers? (?:portal|site|account)|"
    r"talent (?:network|community))\b",
    re.IGNORECASE,
)


def _about_a_job(email: Email) -> bool:
    address = parseaddr(email.sender)[1].lower()
    return (any(site in address for site in _GENERIC_DOMAINS if site != "gmail.com")
            or bool(re.search(r"career|recruit|talent|hiring|\bjobs?\b", email.sender, re.IGNORECASE))
            or bool(_JOB_CONTEXT.search(f"{email.subject}\n{email.text[:4000]}")))


def classify(email: Email) -> str:
    kind = _classify(email)
    return OTHER if kind == VERIFICATION and not _about_a_job(email) else kind


def _classify(email: Email) -> str:
    if "SENT" in email.labels or is_marketing(email):  # your own replies aren't applications
        return OTHER
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
    r"position|role|graduate|grad|trainee|apprentice|careers?|program|programme|co-?op|sdet|sde|swe|qa)\b",
    re.IGNORECASE,
)
_GENERIC_SENDERS = re.compile(
    r"^(no-?reply|do-?not-?reply|donotreply|notifications?|greenhouse|workday|lever|ashby|smartrecruiters|icims|"
    r"taleo|jobvite|workable|tsenta.*|human resources|hr|recruiting|careers?|talent( acquisition)?|hiring( team)?|"
    r"jobs?|team|.*\.sender|workdaysystem.*)$",
    re.IGNORECASE,
)
_JOB_SITES = re.compile(
    r"\b(?:greenhouse|workday|lever|ashby|smartrecruiters|icims|taleo|jobvite|workable|dayforce)\b", re.IGNORECASE,
)
_GENERIC_DOMAINS = (
    "gmail.com", "greenhouse.io", "greenhouse-mail.io", "lever.co", "myworkday.com", "myworkdayjobs.com",
    "ashbyhq.com", "smartrecruiters.com", "icims.com", "taleo.net", "jobvite.com", "workablemail.com",
    "successfactors.com", "tsenta", "applytojob.com", "bamboohr.com", "recruitee.com", "breezy.hr", "paylocity.com",
    "ultipro.com", "oraclecloud.com", "eightfold.ai", "phenom", "avature", "jazzhr", "dayforce", "greenhouse-jobs.com",
    "paycomonline.com",
)
_SENDER_NOISE = re.compile(
    r"\b(hiring team|hiring|recruiting team|recruiting|recruitment|talent acquisition|talent team|talent|careers?|"
    r"jobs at|jobs|human resources|hr|people team|team|inbox|no-?reply|donotreply|do not reply)\b",
    re.IGNORECASE,
)

_COMPANY_PATTERNS = [
    # "... at Affirm"
    r"\b(?i:role|position|job|opening|internship|opportunity|engineer\w*|developer|analyst|intern|team|\))\s+(?i:at|with)\s+(?P<c>[A-Z0-9][\w&.,'’ -]{1,60}?)(?=\s*(?:[!?.:;|(]|\s[-–—]\s|,\s|\bfor\b|\band\b|$))",
    r"\b(?i:at)\s+(?P<c>[A-Z0-9][\w&.'’ -]{1,60}?)(?=\s*(?:[!?.;|]|\s[-–—]\s|\sby\b|$))",
    # "interest in (joining) Citi!"
    r"(?i:interest in (?:joining |working (?:at|with|for) )?)(?!(?i:the|our|a|an|this)\b)(?P<c>[A-Z0-9][\w&.'’ -]{1,60}?)(?=\s*(?:[!?.;,|]|\s(?:and|for|as)\b|$))",
    # "applying to Aurora", "Application With ZEFR", "Applying to Ensign Services"
    r"(?i:(?:applying|applied|application|apply)\s+(?:to|with|at)\s+(?:the\s+)?)(?P<c>[A-Z0-9][\w&.,'’() -]{1,70}?)(?=\s*(?:[!?.;|]|\s[-–—]\s|,\s|\bfor\b|\band\s+(?:are|we|will|have|is|our)\b|$))",
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
    # lowercase names: "Thanks for applying to neurohire.ai"
    r"(?i:applying|applied|application)\s+(?i:to|at|with)\s+(?P<c>[a-z][\w.-]{2,40})\s*[!.]?\s*$",
    # "onsemi Your Recent Application-AI Engineer"
    r"^(?P<c>[a-z][\w&.'’-]{1,30})\s+(?i:your (?:recent )?(?:job )?application)",
    # "Thank You from EBSCO Information Services, LLC"
    r"^(?i:thank you|thanks)\s+from\s+(?P<c>[A-Z0-9][\w&.,'’ -]{1,60}?)\s*[!.]?\s*$",
    # "Leidos -Thank You For Applying ..."
    r"^(?P<c>[A-Z0-9][\w&.'’ ]{1,40}?)\s*[-–—:]\s*(?i:thank)",
    # "FedEx Freight Application Status Update"
    r"^(?P<c>[A-Z0-9][\w&.'’ ]{1,40}?)\s+(?i:application|candidate)\s+(?i:status\s+)?(?i:update)",
    # Sign-offs like "Morgan Stanley Talent Acquisition"
    r"^(?P<c>[A-Z0-9][\w&.'’ ]{1,40}?)(?:\s+(?:Global|Careers))?\s+(?:Talent Acquisition|Recruiting|Recruitment|Human Resources)(?:\s+Team)?\s*$",
]

# Words that mark a company name even next to a role word ("Ascent Developer Solutions").
_COMPANY_WORDS = re.compile(
    r"\b(solutions|technologies|systems|labs|holdings|partners|inc|llc|corp|corporation|ltd|bank|cooperative)\b",
    re.IGNORECASE,
)
# "... Intern and are currently reviewing ...": the sentence carries on after the role.
_ROLE_END = re.compile(r"\s+and\s+(?:are|we|will|have|is|our)\b.*", re.IGNORECASE | re.DOTALL)

_ROLE_PATTERNS = [
    r"for the position\s*[-–:]\s*(?P<r>[^!?\n]{3,90}?)(?=\s{2,}|\s+We\b|[.!]|$)",
    r"^(?P<r>[^!?|\n]{3,90}?)\s+Application\s+(?:Status\s+)?Update",
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
    value = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", value)  # zero-width and direction marks
    value = re.sub(r"\s+", " ", value).strip(" \t-–—:|,.!?\"'*")
    value = re.sub(r"^(?:the|our)\s+", "", value, flags=re.IGNORECASE)
    return value.strip()


def _looks_like_role(text: str) -> bool:
    return bool(_ROLE_WORDS.search(text)) or bool(re.search(r"\b\d{5,}\b", text))


def _company_from_text(text: str) -> str:
    for pattern in _COMPANY_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.MULTILINE):
            candidate = _clean(match.group("c"))
            if not candidate or len(candidate) > 60 or (_looks_like_role(candidate) and not _COMPANY_WORDS.search(candidate)):
                continue
            if candidate.lower() in {"you", "us", "our team", "manan", "this", "it", "the team"}:
                continue
            return candidate
    return ""


# Workday address names that don't read as the company on their own.
_WORKDAY_TENANTS = {
    "selinc": "SEL", "freight": "FedEx Freight", "elevancehealth": "Elevance Health",
    "trinitylifesciences": "Trinity Life Sciences", "bah": "Booz Allen Hamilton", "ms": "Morgan Stanley",
}


def _company_from_sender(sender: str) -> str:
    name, address = parseaddr(sender)
    name = re.sub(r"^.{1,30}?\s+from\s+", "", name, flags=re.IGNORECASE)  # "Miles from Avis Budget"
    name = re.sub(r"^(?:donotreply|do-?not-?reply|no-?reply)[_ -]+|[_ -]+(?:hr|careers|jobs)$", "", name, flags=re.IGNORECASE)
    if _JOB_SITES.search(name):
        name = _clean(re.sub(r"\s*(?:@|-)?\s*" + _JOB_SITES.pattern + r"\s*", " ", name, flags=re.IGNORECASE))
        name = re.sub(r"\b(?:notifications?|support|system)\b", "", name, flags=re.IGNORECASE).strip()
        if len(name) < 3 or "@" in name:  # "ms workday", "Workday@bah.com": use the address instead
            name = ""
    cleaned = _clean(_SENDER_NOISE.sub("", name.replace("’s", "").replace("'s", "")))
    cleaned = re.sub(r"[,.]+$", "", cleaned).strip()
    if name and not _GENERIC_SENDERS.match(name.strip()) and len(cleaned) >= 2:
        return cleaned.title() if cleaned.islower() else cleaned
    domain = address.rsplit("@", 1)[-1].lower() if "@" in address else ""
    local = address.split("@", 1)[0].lower()
    # Workday sends from <company>@myworkday.com, e.g. copart@myworkday.com.
    if domain.endswith("myworkday.com") and len(local) >= 3 and not _GENERIC_SENDERS.match(local):
        return _WORKDAY_TENANTS.get(local, local.title())
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
            role = _clean(_ROLE_END.sub("", match.group("r")))
            if role and _looks_like_role(role) and len(role) <= 90:
                return role
    return ""


# ---------------------------------------------------------------- cleanup

# Sentence carrying on after a company name: "Navy Federal Credit Union has been received".
_COMPANY_TAIL = re.compile(
    r"\s+(?:has|have been|is|are|was|were|itself|using|via|and (?:our|are|we|will|is|the)|staff positions)\b.*"
    # a role stuck on the end: "Independent Bank AI Engineer"
    r"|\s+(?:(?:AI|ML|Data|Software|Senior|Junior|Lead|Associate)\s+){0,2}(?:engineer|intern|internship|analyst|developer|scientist)$"
    r"|\s+[-–—|]\s+.*$",
    re.IGNORECASE,
)
_COMPANY_ATS = re.compile(
    r"^(?:my\s*workday|workday)\s+|\s+(?:workday|@\s*icims|@\s*\w+(?:\.\w+)+)$", re.IGNORECASE,
)
_LEGAL_SUFFIX = re.compile(r",?\s+(?:mfg\.?\s+)?(?:inc\.?|incorporated|llc|l\.l\.c\.|ltd\.?|corp\.?)$", re.IGNORECASE)
# Openers that are a sentence, not a name: "You're in the Game – Thanks for Applying!"
_NOT_A_COMPANY = re.compile(r"^(?:you|you['’]re|your|we|we['’]re|our|thank|thanks|this|that|it|hi|hello|dear)\b",
                            re.IGNORECASE)
# Words the patterns sometimes catch that are never an employer.
_JUNK_NAMES = {"the", "job", "jobs", "jr", "team", "dear", "dear naman", "hi naman", "naman", "thank you", "thanks",
               "candidate experience site", "careers", "career site", "application", "hiring", "applicantemails",
               "application received", "application update", "next steps", "excellence", "update", "updates"}

# Different spellings of the same employer, so their emails land on one row.
_ALIASES = {
    "bah": "Booz Allen Hamilton", "booz allen hamilton_united states": "Booz Allen Hamilton",
    "pnnl": "Pacific Northwest National Laboratory", "cook": "Cook Medical", "cook group": "Cook Medical",
    "microstrategy services": "Strategy", "microstrategy": "Strategy", "j.m": "The J.M. Smucker Co.",
    "jpmorganchase": "JPMorgan Chase", "jpmorgan chase & co": "JPMorgan Chase", "jpmorgan chase & co.": "JPMorgan Chase",
    "slfworkdaynotifications": "Sun Life", "sunlife": "Sun Life", "deltadentalmo": "Delta Dental of Missouri",
    "7eleven": "7-Eleven", "purestorage": "Everpure", "freight": "FedEx Freight", "ebsco information services": "EBSCO",
    "ebscoind": "EBSCO", "sel": "Schweitzer Engineering Laboratories (SEL)", "selinc": "Schweitzer Engineering Laboratories (SEL)",
}


def tidy_company(name: str) -> str:
    """Trim a found company name down to the name, or return "" if it isn't one."""
    name = html.unescape(name or "").replace("\xa0", " ")
    name = re.sub(r"[^\w\s&.,'’()@|:–—-]", "", name)  # emoji and symbols: "Next Steps 🍿"
    name = _clean(_COMPANY_ATS.sub("", _clean(name)))
    name = _clean(_COMPANY_TAIL.sub("", name))
    if not name or _NOT_A_COMPANY.match(name):
        return ""
    if name.isupper() and len(name) > 5:  # "DAIKIN COMFORT TECHNOLOGIES MFG INC"
        name = name.title()
    name = _clean(_LEGAL_SUFFIX.sub("", name))
    key = name.lower().rstrip(".")
    if key in _ALIASES:
        return _ALIASES[key]
    if len(name) < 2 or key in _JUNK_NAMES:
        return ""
    return name


# Requisition numbers: "R-121905", "REQ380441", "JR2027784", "(ID 2026-2112)", "[2026-12640]", "- 169810".
_REQ_ID = re.compile(
    r"^(?:R-?\d{4,}|REQ\d{4,}|JR\d{4,})\s+|\s*[(\[](?:ID |Job (?:number|ID):?\s*|Req(?:uisition)? ?#?\s*)?[\w-]*\d{4,}[\w-]*[)\]]"
    r"|\s+[-–]\s+(?:JR|R-?|REQ)?\d{4,}\b|\s+(?:JR|REQ)\d{4,}\b|-R\d{5,}\b",
    re.IGNORECASE,
)
# Sentence carrying on after the role: "Data Test Analyst I has been received", "role. If you ..."
_ROLE_TAIL = re.compile(
    r"(?:(?<!Jr)(?<!Sr)\.\s|\s+(?:has been|have been|was|is currently|is being|will be|job, you can|we\b|at\s+[A-Z]))(?:.|\n)*$"
    r"|\s+(?:position|role|job|opportunity)\.?$",
)
_ROLE_PLACE = re.compile(r"\s*\((?:[A-Z][\w .]+,\s*[A-Z]{2}|Remote|Hybrid|Onsite|Open|Bachelors|Masters)\)\s*$")
_NOT_A_ROLE = re.compile(r"^(?:this|that|a|an|the|our|your|role|position|job)\b\.?\s*(?:position|role|job)?$|^role\b|^this\b",
                         re.IGNORECASE)


def tidy_role(role: str, company: str = "") -> str:
    role = html.unescape(role or "").replace("\xa0", " ")
    role = _clean(role)
    # "Snowflake | AI Research Scientist", "Kairos Power - Applications Integration Engineer"
    if company and role.lower().startswith(company.lower()):
        role = re.sub(r"^\s*[|:–—-]\s*", "", role[len(company):]) if re.match(r"\s*[|:–—-]", role[len(company):]) else role
    # "Naman Dewan - R0173771 Entry Level Software Engineer": your name, then the requisition number
    role = re.sub(r"^[A-Z][a-z]+ [A-Z][a-z]+\s*[-–]\s*(?=(?:R|REQ|JR)?-?\d{4,}\b)", "", role)
    for _ in range(3):
        role = _clean(_ROLE_TAIL.sub("", _clean(role)))
        role = _clean(_REQ_ID.sub(" ", role))
        role = _clean(_ROLE_PLACE.sub("", role))
    role = re.sub(r"^(?:a|an)\s+(?=[A-Z])", "", role)  # "a Analyst - Process Analytics"
    role = re.sub(r"^(?:position|role) of\s+", "", role, flags=re.IGNORECASE)
    if not role or _NOT_A_ROLE.match(role) or not _looks_like_role(role) or len(role) > 90:
        return ""
    return role


def _real_sender(email: Email) -> str:
    """Tsenta forwards company mail from its own inbox; the footer names the real sender."""
    if "tsenta" in email.sender.lower():
        found = re.search(r"Sent From:\s*(\S+@[\w.-]+)", email.text)
        if found:
            return found.group(1)
    return email.sender


# Subject pieces that are never the role: "Interview - SDET I - Modivcare"
_SUBJECT_NOISE = re.compile(
    r"^(?:interview|interview invitation|application|application update|application status|application received|"
    r"assessment|next steps?|update|thank you|thanks|re|fwd?)$",
    re.IGNORECASE,
)


def _role_from_subject_parts(subject: str, company: str) -> str:
    """"Interview - SDET I - Modivcare": the piece that's neither the company nor a generic word."""
    parts = [_clean(p) for p in re.split(r"\s+[-–—|]\s+", subject)]
    if len(parts) < 2:
        return ""
    rest = [p for p in parts if p and not _SUBJECT_NOISE.match(p)
            and normalize_company(p) != normalize_company(company or "-")]
    return rest[0] if len(rest) == 1 else ""


def extract(email: Email) -> Extracted:
    first_lines = "\n".join(email.text.splitlines()[:15])[:1500]
    company = (tidy_company(_company_from_text(email.subject)) or tidy_company(_company_from_text(first_lines))
               or tidy_company(_company_from_sender(_real_sender(email))))
    role = (tidy_role(_role_from_text(email.subject), company)
            or tidy_role(_role_from_text(first_lines), company)
            or tidy_role(_role_from_subject_parts(email.subject, company), company)
            or tidy_role(_role_from_text(email.text[1500:4000]), company))
    if role.lower() == company.lower():  # "Thank you for applying to Ascent Developer Solutions"
        role = ""
    return Extracted(company=company, role=role)


# ---------------------------------------------------------------- next action

_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10, "fourteen": 14}
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_WITHIN = re.compile(
    r"\b(?:within|in the next|next|in|expires? in|valid for|available for|have)\s+(\d{1,2}|one|two|three|four|five|six|"
    r"seven|ten|fourteen)\s+(business |calendar |working )?(days?|hours?)\b",
    re.IGNORECASE,
)
_BY_DATE = re.compile(
    r"\b(?:by|before|no later than|expires?(?: on)?|deadline(?: is|:)?|due(?: date| on| by)?:?|until|complete it by)\s+"
    r"(?:(?:mon|tues|wednes|thurs|fri|satur|sun)day,?\s+)?"
    r"(?:(?P<month>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,?\s+(?P<year>\d{4}))?"
    r"|(?P<m2>\d{1,2})/(?P<d2>\d{1,2})(?:/(?P<y2>\d{2,4}))?)",
    re.IGNORECASE,
)
_ASKS_AVAILABILITY = re.compile(
    r"your availability|dates and times|times that work|time slots?|schedule (?:a|your|the) (?:time|call|interview)|"
    r"calendly\.com|book a time|select a time|pick a time",
    re.IGNORECASE,
)


def deadline(text: str, sent: str) -> "date | None":
    """The date something is due, from "within 5 days", "by November 3" or "expires on 11/02/2026"."""
    from datetime import date, timedelta

    try:
        start = date.fromisoformat(sent)
    except ValueError:
        return None
    found = _BY_DATE.search(text)
    if found:
        try:
            if found.group("month"):
                month, day = _MONTHS[found.group("month").lower()[:3]], int(found.group("day"))
                year = int(found.group("year") or start.year)
            else:
                month, day = int(found.group("m2")), int(found.group("d2"))
                year = int(found.group("y2") or start.year)
                year += 2000 if year < 100 else 0
            due = date(year, month, day)
            if due < start and not (found.group("year") or found.group("y2")):
                due = date(year + 1, month, day)  # "by January 5" written in December
            if start <= due <= start + timedelta(days=60):
                return due
        except (ValueError, KeyError):
            pass
    found = _WITHIN.search(text)
    if found:
        n = found.group(1).lower()
        n = _NUMBERS.get(n) or int(n)
        if found.group(3).lower().startswith("hour"):
            return start + timedelta(days=max(1, n // 24))
        if (found.group(2) or "").strip().lower() in ("business", "working"):
            due = start
            while n:
                due += timedelta(days=1)
                n -= due.weekday() < 5
            return due
        return start + timedelta(days=n)
    return None


def next_action(email: Email, kind: str) -> str:
    """What you need to do about this email, for the Next action column and the reminders."""
    text = f"{email.subject}\n{email.text[:6000]}"
    due = deadline(text, email.date)
    when = f" by {due:%a %-d %b}" if due else ""
    if kind == ASSESSMENT:
        return f"Complete the assessment{when}"
    if kind == INTERVIEW:
        if _ASKS_AVAILABILITY.search(text):
            return f"Reply with your availability{when}"
        return f"Prepare for the interview{when}"
    if kind == OFFER:
        return f"Respond to the offer{when}"
    return ""
