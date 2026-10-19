# FRIDAY: job application tracker

Reads your Gmail, finds the confirmation emails Tenta AI sends when it applies
to a job for you, and logs each application (company, role, location, link,
date) in a Google Sheet. If no Sheet is configured it writes `applications.csv`.

This is phase 1 of the plan. Status tracking from company replies, Claude
classification, scheduling and the daily digest come next.

## How it works

1. Searches Gmail with `TENTA_QUERY` (read-only access).
2. Parses each matching email with `tracker/tenta_parser.py`. It handles
   labelled fields (`Company: …`, `Role: …`), batch emails listing several jobs,
   and sentences like "applied to the Data Analyst role at Acme".
3. Skips emails it has already processed and jobs already in the sheet
   (same company + title).
4. Appends new rows. Emails it couldn't parse are listed in `unparsed.csv` so
   the parser can be improved.

## One-time setup (about 20 minutes)

1. **Python 3.10+**, then:
   ```bash
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   ```
2. **Google Cloud credentials**
   - Go to <https://console.cloud.google.com/>, create a project (e.g. "FRIDAY").
   - APIs & Services → Library → enable **Gmail API** and **Google Sheets API**.
   - APIs & Services → OAuth consent screen → External, add your own Gmail as a
     **test user**.
   - APIs & Services → Credentials → Create credentials → OAuth client ID →
     **Desktop app** → download the JSON and save it here as `credentials.json`.
3. **Google Sheet** (optional): create an empty sheet and put the long ID from
   its URL (`docs.google.com/spreadsheets/d/<THIS_PART>/edit`) in `.env` as
   `SHEET_ID`. The script adds an `Applications` tab with headers.
4. **Tenta sender**: open one Tenta confirmation email, check the sender
   address, and set `TENTA_QUERY` in `.env`, e.g.
   `TENTA_QUERY=from:notifications@tenta.ai newer_than:60d`.

## Run it

```bash
python -m tracker.main --dry-run   # first run opens a browser to log in; prints what it found
python -m tracker.main             # saves to the Sheet / applications.csv
```

The login creates `token.json`. Keep it and `credentials.json` private (both
are in `.gitignore`).

## Tests

```bash
python -m unittest discover -s tests -t .
```

`samples/placeholder_*.txt` are made-up emails. Add real Tenta emails there
(personal details blanked out) and a test for each, then tighten the parser.
