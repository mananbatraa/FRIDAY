"""Where applications are saved: a Google Sheet, or a local CSV as a fallback."""
import csv
import os
from datetime import date

from .models import Application

COLUMNS = [
    "ID", "Company", "Job title", "Location", "Job link", "Applied on", "Status",
    "Last update", "Next action", "Deadline", "Email link", "Notes", "Source message ID",
]


def _row(app: Application) -> list[str]:
    return [
        app.id, app.company, app.job_title, app.location, app.job_link, app.applied_on, app.status,
        date.today().isoformat(), "", "", app.email_link, app.notes, app.source_message_id,
    ]


def _key_from_row(row: dict) -> str:
    return Application(company=row.get("Company", ""), job_title=row.get("Job title", "")).key


class CsvStorage:
    def __init__(self, path: str = "applications.csv"):
        self.path = path

    def _read(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def known(self) -> tuple[set[str], set[str]]:
        rows = self._read()
        return {r["Source message ID"] for r in rows}, {_key_from_row(r) for r in rows}

    def append(self, apps: list[Application]) -> None:
        new_file = not os.path.exists(self.path)
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(COLUMNS)
            writer.writerows(_row(a) for a in apps)


class SheetStorage:
    TAB = "Applications"

    def __init__(self, creds, sheet_id: str):
        from googleapiclient.discovery import build

        self.sheets = build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()
        self.sheet_id = sheet_id
        self._ensure_tab()

    def _ensure_tab(self) -> None:
        meta = self.sheets.get(spreadsheetId=self.sheet_id).execute()
        titles = {s["properties"]["title"] for s in meta["sheets"]}
        if self.TAB not in titles:
            self.sheets.batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": self.TAB, "gridProperties": {"frozenRowCount": 1}}}}]},
            ).execute()
        header = self.sheets.values().get(spreadsheetId=self.sheet_id, range=f"{self.TAB}!1:1").execute()
        if not header.get("values"):
            self.sheets.values().update(
                spreadsheetId=self.sheet_id, range=f"{self.TAB}!A1",
                valueInputOption="RAW", body={"values": [COLUMNS]},
            ).execute()

    def known(self) -> tuple[set[str], set[str]]:
        result = self.sheets.values().get(spreadsheetId=self.sheet_id, range=self.TAB).execute()
        values = result.get("values", [])
        if not values:
            return set(), set()
        header, rows = values[0], values[1:]
        dicts = [dict(zip(header, r)) for r in rows]
        return {d.get("Source message ID", "") for d in dicts}, {_key_from_row(d) for d in dicts}

    def append(self, apps: list[Application]) -> None:
        self.sheets.values().append(
            spreadsheetId=self.sheet_id, range=f"{self.TAB}!A1",
            valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
            body={"values": [_row(a) for a in apps]},
        ).execute()
