"""Two tables: Applications (one row per job) and Emails (one row per processed email).

Stored as tabs in a Google Sheet, or as two CSV files when no Sheet is set.
Each run loads both tables, changes them in memory, and writes them back, so
anything you type into the Notes column is kept.
"""
from __future__ import annotations

import csv
import os

APP_COLUMNS = [
    "Company", "Role", "Status", "Applied on", "Last update", "Next action", "Latest email", "Notes",
]
EMAIL_COLUMNS = ["Date", "Kind", "Company", "Role", "From", "Subject", "Email link", "Message ID"]


class CsvTable:
    def __init__(self, path: str, columns: list[str]):
        self.path, self.columns = path, columns

    def load(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, newline="", encoding="utf-8") as f:
            return [dict(r) for r in csv.DictReader(f)]

    def save(self, rows: list[dict]) -> None:
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


class SheetTable:
    def __init__(self, sheets, sheet_id: str, tab: str, columns: list[str]):
        self.sheets, self.sheet_id, self.tab, self.columns = sheets, sheet_id, tab, columns
        meta = sheets.get(spreadsheetId=sheet_id).execute()
        if tab not in {s["properties"]["title"] for s in meta["sheets"]}:
            sheets.batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": tab, "gridProperties": {"frozenRowCount": 1}}}}]},
            ).execute()

    def load(self) -> list[dict]:
        values = self.sheets.values().get(spreadsheetId=self.sheet_id, range=f"'{self.tab}'").execute().get("values", [])
        if not values:
            return []
        header = values[0]
        return [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in values[1:]]

    def save(self, rows: list[dict]) -> None:
        values = [self.columns] + [[str(r.get(c, "")) for c in self.columns] for r in rows]
        self.sheets.values().update(
            spreadsheetId=self.sheet_id, range=f"'{self.tab}'!A1",
            valueInputOption="USER_ENTERED", body={"values": values},
        ).execute()


def open_tables(creds, sheet_id: str):
    """Return (applications, emails) tables."""
    if not sheet_id:
        return CsvTable("applications.csv", APP_COLUMNS), CsvTable("emails.csv", EMAIL_COLUMNS)
    from googleapiclient.discovery import build

    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()
    return (
        SheetTable(sheets, sheet_id, "Applications", APP_COLUMNS),
        SheetTable(sheets, sheet_id, "Emails", EMAIL_COLUMNS),
    )
