from __future__ import annotations

from dataclasses import dataclass


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


_SUFFIXES = (
    " inc", " inc.", " llc", " ltd", " ltd.", " limited", " pvt", " pvt.", " private",
    " corp", " corp.", " corporation", " co", " co.", " gmbh", " plc", " group",
)


def normalize_company(name: str) -> str:
    name = " ".join(name.lower().replace(",", " ").replace("’", "'").split())
    changed = True
    while changed:
        changed = False
        for suffix in _SUFFIXES:
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()
                changed = True
    return name
