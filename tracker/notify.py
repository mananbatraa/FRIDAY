"""macOS notifications for scheduled runs (does nothing on other systems)."""
from __future__ import annotations

import platform
import subprocess


def notify(title: str, message: str) -> None:
    if platform.system() != "Darwin":
        return
    script = f"display notification {_quote(message)} with title {_quote(title)}"
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
