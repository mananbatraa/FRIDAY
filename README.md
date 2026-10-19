# FRIDAY: job application tracker

Reads your Gmail, finds the emails companies send when you apply (Tsenta AI
applies with your address, so confirmations come straight from each company
or its job site: Greenhouse, Workday, Lever, Ashby and so on), and keeps a
tracker of every application and its status in a Google Sheet. Without a
Sheet it writes `applications.csv` and `emails.csv`.

## How it works

1. Searches Gmail (read-only) for job-related emails from the last `DAYS` days.
2. Sorts each new email into a kind: **Applied**, **Assessment**, **Interview**,
   **Offer**, **Rejected**, **Verification** (security codes, identity checks)
   or **Other**, and finds the company and role.
   - By default this uses built-in rules (`tracker/job_emails.py`).
   - With `ANTHROPIC_API_KEY` set (Python 3.10+), Claude reads each email
     instead, which handles unusual wording better. Rules are the fallback.
3. Updates the **Applications** tab: one row per company + role. Status only
   moves forward (Applied → Assessment → Interview → Offer), except Rejected,
   which can come at any stage. Your Notes column is never touched.
4. Logs every processed email in the **Emails** tab, so nothing is counted
   twice and you can check why a row has its status.

## One-time setup (about 20 minutes)

1. **Python 3.9+**, then:
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
4. **Claude (optional)**: put an API key from <https://console.anthropic.com/>
   in `.env` as `ANTHROPIC_API_KEY`. Needs Python 3.10+ (`python3 --version`).

## Run it

```bash
python -m tracker.main --dry-run   # first run opens a browser to log in; prints what it found
python -m tracker.main             # saves to the Sheet / CSV files
python -m tracker.main --days 90   # look further back
```

The login creates `token.json`. Keep it and `credentials.json` private (both
are in `.gitignore`).

## Dashboard

```bash
streamlit run dashboard.py
```

Opens in your browser: totals, applications per day, where each application
stands, a "needs your attention" list (interviews, assessments, offers and
recent security-code emails), and a searchable table of everything. It reads
the same Sheet or CSV files the tracker writes; press **Refresh** after a run.

## Tests

```bash
python -m unittest discover -s tests -t .
```

`tests/test_job_emails.py` holds real subject lines and previews. When the
rules get an email wrong, add it there and adjust `tracker/job_emails.py`.
