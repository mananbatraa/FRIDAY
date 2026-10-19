from dataclasses import dataclass, field


@dataclass
class Email:
    id: str
    thread_id: str
    sender: str
    subject: str
    date: str  # ISO date, YYYY-MM-DD
    text: str

    @property
    def gmail_link(self) -> str:
        return f"https://mail.google.com/mail/u/0/#all/{self.id}"


@dataclass
class Application:
    company: str
    job_title: str
    location: str = ""
    job_link: str = ""
    applied_on: str = ""
    status: str = "Applied"
    email_link: str = ""
    source_message_id: str = ""
    notes: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{normalize_company(self.company)}|{self.job_title.strip().lower()}"

    @property
    def id(self) -> str:
        slug = "-".join(
            part for part in (normalize_company(self.company), self.job_title.lower(), self.applied_on) if part
        )
        return "".join(c if c.isalnum() else "-" for c in slug).strip("-")


_SUFFIXES = (
    " inc", " inc.", " llc", " ltd", " ltd.", " limited", " pvt", " pvt.", " private",
    " corp", " corp.", " corporation", " co", " co.", " gmbh", " plc",
)


def normalize_company(name: str) -> str:
    name = " ".join(name.lower().replace(",", " ").split())
    changed = True
    while changed:
        changed = False
        for suffix in _SUFFIXES:
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()
                changed = True
    return name
