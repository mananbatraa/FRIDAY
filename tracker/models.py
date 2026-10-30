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
    labels: tuple = ()  # Gmail label IDs, e.g. CATEGORY_PROMOTIONS
    account: str = ""  # the Gmail address it was read from ("" = the main account)

    @property
    def gmail_link(self) -> str:
        return gmail_url(self.id, self.account)


def gmail_url(message_id: str, account: str = "") -> str:
    """A link that opens the email in the right Gmail account when you're signed in to several."""
    return f"https://mail.google.com/mail/u/{account or 0}/#all/{message_id}"


_SUFFIXES = (
    " inc", " inc.", " llc", " ltd", " ltd.", " limited", " pvt", " pvt.", " private",
    " corp", " corp.", " corporation", " co", " co.", " gmbh", " plc", " group",
    # Longer and shorter forms of one name: "Infineon Technologies" / "Infineon", "Slipstream IT" / "Slipstream".
    " technologies", " enterprises", " international", " solutions", " broadcast", " companies", " it", " family",
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
    return name.replace(" ", "")  # "Vori Health" and "Vorihealth" are one company
