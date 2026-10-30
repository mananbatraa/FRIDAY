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

    @property
    def gmail_link(self) -> str:
        return f"https://mail.google.com/mail/u/0/#all/{self.id}"


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
