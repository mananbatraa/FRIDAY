from __future__ import annotations

import os
from dataclasses import dataclass

from .job_emails import DEFAULT_QUERY


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader so there's one less dependency."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Config:
    days: int
    job_query: str
    sheet_id: str
    credentials_file: str
    token_file: str
    claude_model: str
    outreach_query: str = ""  # empty: outreach tracking is off
    follow_up_days: int = 7
    also_read: tuple = ()  # more Gmail addresses to read, each with its own login file

    def accounts(self) -> list[tuple[str, str]]:
        """(address, login file) for every Gmail account to read; the main one has no fixed address."""
        extra = [(a, f"token_{a.split('@')[0].replace('.', '_')}.json") for a in self.also_read]
        return [("", self.token_file)] + extra

    @classmethod
    def load(cls) -> "Config":
        _load_dotenv()
        days = int(os.environ.get("DAYS", "30"))
        return cls(
            days=days,
            job_query=os.environ.get("JOB_QUERY") or DEFAULT_QUERY.format(days=days),
            sheet_id=os.environ.get("SHEET_ID", ""),
            credentials_file=os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
            token_file=os.environ.get("GOOGLE_TOKEN_FILE", "token.json"),
            claude_model=os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"),
            outreach_query=os.environ.get("OUTREACH_QUERY", "").strip(),
            follow_up_days=int(os.environ.get("FOLLOW_UP_DAYS", "7")),
            also_read=tuple(a.strip() for a in os.environ.get("ALSO_READ_GMAIL", "").split(",") if a.strip()),
        )
