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
        return [m["id"] for m in self.search_messages(query, limit)]

    def search_messages(self, query: str, limit: int = 500) -> list[dict]:
        """Like search, but each match is {"id": ..., "threadId": ...}."""
        found: list[dict] = []
        request = self.service.users().messages().list(userId="me", q=query, maxResults=min(limit, 500))
        while request is not None and len(found) < limit:
            response = request.execute(num_retries=RETRIES)
            found.extend(response.get("messages", []))
            request = self.service.users().messages().list_next(request, response)
        return found[:limit]

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
            labels=tuple(msg.get("labelIds", [])),
        )

    def thread(self, thread_id: str) -> list[dict]:
        """Every message in a Gmail thread, oldest first, with just the headers outreach tracking needs."""
        time.sleep(PAUSE_SECONDS)
        thread = self.service.users().threads().get(
            userId="me", id=thread_id, format="metadata", metadataHeaders=_THREAD_HEADERS,
        ).execute(num_retries=RETRIES)
        messages = []
        for msg in thread.get("messages", []):
            headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
            sent = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc)
            messages.append({
                "id": msg["id"], "thread_id": msg["threadId"], "date": sent.date().isoformat(),
                "from": headers.get("from", ""), "to": headers.get("to", ""), "subject": headers.get("subject", ""),
                "auto": _is_auto_reply(headers), "labels": tuple(msg.get("labelIds", [])),
            })
        return sorted(messages, key=lambda m: m["date"])

    def label_id(self, name: str) -> str:
        """ID of the Gmail label (folder) called `name`, creating it if it's missing."""
        labels = self.service.users().labels().list(userId="me").execute(num_retries=RETRIES)
        for label in labels.get("labels", []):
            if label["name"].lower() == name.lower():
                return label["id"]
        if "/" in name:  # Gmail only nests a label when its parent exists
            self.label_id(name.rsplit("/", 1)[0])
        body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        return self.service.users().labels().create(userId="me", body=body).execute(num_retries=RETRIES)["id"]

    def move(self, message_ids: list[str], label_id: str) -> None:
        """Like Gmail's "Move to": add the label and take the messages out of the inbox."""
        for start in range(0, len(message_ids), 1000):  # batchModify takes at most 1000 IDs
            body = {"ids": message_ids[start:start + 1000], "addLabelIds": [label_id], "removeLabelIds": ["INBOX"]}
            self.service.users().messages().batchModify(userId="me", body=body).execute(num_retries=RETRIES)

    def arrival(self, message_id: str) -> tuple[datetime, bool]:
        """When a message arrived, and whether it's already in the trash."""
        time.sleep(PAUSE_SECONDS)
        msg = self.service.users().messages().get(userId="me", id=message_id, format="minimal").execute(num_retries=RETRIES)
        received = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc)
        return received, "TRASH" in msg.get("labelIds", [])

    def trash(self, message_ids: list[str]) -> None:
        """Move messages to Gmail's Trash, which Gmail empties after 30 days."""
        for message_id in message_ids:
            time.sleep(PAUSE_SECONDS)
            self.service.users().messages().trash(userId="me", id=message_id).execute(num_retries=RETRIES)


_THREAD_HEADERS = ["From", "To", "Subject", "Auto-Submitted", "X-Autoreply", "X-Autorespond", "Precedence"]


def _is_auto_reply(headers: dict) -> bool:
    """Out-of-office and other automatic replies, which shouldn't count as someone answering."""
    if headers.get("auto-submitted", "no").lower() != "no" or "x-autoreply" in headers or "x-autorespond" in headers:
        return True
    if headers.get("precedence", "").lower() == "auto_reply":
        return True
    return bool(re.match(r"(?i)\s*(automatic reply|auto(matic)?[- ]?reply|out of (the )?office|auto:)",
                         headers.get("subject", "")))


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
        return html.unescape("\n".join(plain)).replace("\xa0", " ")
    return "\n".join(_html_to_text(h) for h in _walk(payload, "text/html"))
