from __future__ import annotations

import json
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Mail access to read job emails and move them into folders (it never sends or
# deletes); Sheets access only to write the tracker sheet.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
]


class LoginNeeded(Exception):
    """The saved Google login is missing or expired and no browser login is allowed."""


def get_credentials(credentials_file: str, token_file: str, interactive: bool = True) -> Credentials:
    """Load the saved token, refreshing it or running the browser login if needed.

    Google expires logins for apps in "Testing" mode after about 7 days; with
    interactive=False (scheduled runs) that raises LoginNeeded instead of
    opening a browser nobody is watching.
    """
    creds = None
    if os.path.exists(token_file):
        with open(token_file) as f:
            granted = json.load(f).get("scopes") or []
        # A login saved before FRIDAY needed more access must be redone.
        if set(SCOPES) <= set(granted):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None
    if not creds or not creds.valid:
        if not interactive:
            raise LoginNeeded("Google login expired or needs new access. Open FRIDAY.command once to log in again.")
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        creds = flow.run_local_server(port=0)
    with open(token_file, "w") as f:
        f.write(creds.to_json())
    return creds
