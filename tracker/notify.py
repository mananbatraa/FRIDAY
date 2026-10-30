"""Notifications for scheduled runs: on the Mac, and on your phone through ntfy when NTFY_TOPIC is set."""
from __future__ import annotations

import os
import platform
import subprocess
import urllib.request

NTFY_SERVER = "https://ntfy.sh"


def notify(title: str, message: str) -> None:
    if platform.system() == "Darwin":
        script = f"display notification {_quote(message)} with title {_quote(title)}"
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if topic:
        try:
            send_ntfy(topic, title, message)
        except OSError:
            pass  # the Mac notification above still went out


def send_ntfy(topic: str, title: str, message: str) -> None:
    """Push to the ntfy app on your phone (subscribe to the same topic there)."""
    request = urllib.request.Request(
        f"{NTFY_SERVER}/{topic}", data=message.encode("utf-8"),
        headers={"Title": title.encode("utf-8").decode("latin-1", "replace")}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise OSError(f"ntfy answered {response.status}")


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
