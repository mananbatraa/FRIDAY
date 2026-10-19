import os
from dataclasses import dataclass


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
    tenta_query: str
    sheet_id: str
    credentials_file: str
    token_file: str

    @classmethod
    def load(cls) -> "Config":
        _load_dotenv()
        return cls(
            tenta_query=os.environ.get("TENTA_QUERY", "from:(tenta) newer_than:60d"),
            sheet_id=os.environ.get("SHEET_ID", ""),
            credentials_file=os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
            token_file=os.environ.get("GOOGLE_TOKEN_FILE", "token.json"),
        )
