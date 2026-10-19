from __future__ import annotations

import base64
import html
import re
import time
from datetime import datetime, timezone

from googleapiclient.discovery import build

from .models import Email

# On a rate-limit error the Google client waits and retries with growing pauses
# (about 1s, 2s, 4s ... up to ~2 minutes in total) before giving up.
RETRIES = 7
# Small pause between messages to stay under Gmail's per-minute quota.
PAUSE_SECONDS = 0.1


class GmailClient:
    def __init__(self, creds):
        self.service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def search(self, query: str, limit: int = 500) -> list[str]:
        """Return message IDs matching a Gmail search query, newest first."""
        ids: list[str] = []
        request = self.service.users().messages().list(userId="me", q=query, maxResults=min(limit, 500))
        while request is not None and len(ids) < limit:
            response = request.execute(num_retries=RETRIES)
            ids.extend(m["id"] for m in response.get("messages", []))
            request = self.service.users().messages().list_next(request, response)
        return ids[:limit]

    def get(self, message_id: str) -> Email:
        time.sleep(PAUSE_SECONDS)
        msg = self.service.users().messages().get(userId="me", id=message_id, format="full").execute(num_retries=RETRIES)
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        sent = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc)
        return Email(
            id=msg["id"],
            thread_id=msg["threadId"],
            sender=headers.get("from", ""),
            subject=headers.get("subject", ""),
            date=sent.date().isoformat(),
            text=_body_text(msg["payload"]),
        )


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def _walk(part, mime: str) -> list[str]:
    found = []
    if part.get("mimeType") == mime and part.get("body", {}).get("data"):
        found.append(_decode(part["body"]["data"]))
    for child in part.get("parts", []) or []:
        found.extend(_walk(child, mime))
    return found


def _html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style).*?</\1>", "", markup)
    # Keep link targets so the parser can still find job URLs.
    markup = re.sub(r'(?is)<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>|</h\d>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", "", markup))
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _body_text(payload) -> str:
    plain = _walk(payload, "text/plain")
    if plain:
        return "\n".join(plain)
    return "\n".join(_html_to_text(h) for h in _walk(payload, "text/html"))
