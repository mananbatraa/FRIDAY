"""Notifications for scheduled runs: on the Mac, and on your phone through ntfy when NTFY_TOPIC is set."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import urllib.request

NTFY_SERVER = "https://ntfy.sh"


def notify(title: str, message: str, phone: bool = True, actions: list[dict] | None = None) -> None:
    if platform.system() == "Darwin":
        script = f"display notification {_quote(message)} with title {_quote(title)}"
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if topic and phone:
        try:
            send_ntfy(topic, title, message, actions)
        except OSError:
            pass  # the Mac notification above still went out


def send_ntfy(topic: str, title: str, message: str, actions: list[dict] | None = None) -> None:
    """Push to the ntfy app on your phone (subscribe to the same topic there), with buttons to text FRIDAY back."""
    body = {"topic": topic, "title": title, "message": message, "actions": buttons(actions)}
    request = urllib.request.Request(
        f"{NTFY_SERVER}/", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise OSError(f"ntfy answered {response.status}")


def button(label: str, command: str) -> dict:
    """A notification button that texts `command` to FRIDAY (see tracker/inbox.py)."""
    inbox = os.environ.get("NTFY_INBOX_TOPIC", "").strip()
    return {"action": "http", "label": label, "url": f"{NTFY_SERVER}/{inbox}", "method": "POST",
            "body": command, "clear": True}


def buttons(first: list[dict] | None = None) -> list[dict]:
    """`first`, then List, Pending and a page to type anything, up to ntfy's 3 buttons. None without an inbox topic."""
    inbox = os.environ.get("NTFY_INBOX_TOPIC", "").strip()
    if not inbox:
        return []
    standard = [button("List", "list"), button("Pending", "pending"),
                {"action": "view", "label": "Message FRIDAY", "url": f"{NTFY_SERVER}/{inbox}"}]
    chosen = (first or []) + standard
    return chosen[:2] + [standard[2]]  # always keep the way to type a message


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
