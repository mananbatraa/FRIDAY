# FRIDAY: job application tracker

Reads your Gmail, finds the emails companies send when you apply (Tsenta AI
applies with your address, so confirmations come straight from each company
or its job site: Greenhouse, Workday, Lever, Ashby and so on), and keeps a
tracker of every application and its status in a Google Sheet. Without a
Sheet it writes `applications.csv` and `emails.csv`.

## How it works

1. Searches Gmail for job-related emails from the last `DAYS` days.
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
5. Moves each new job email out of the inbox into a Gmail folder (label):
   - **USA Jobs**: application received / thanks for applying, and rejections.
   - **USA Jobs/Actions to be Taken**: online assessments, interviews and offers.

   Security-code and "verify your account" emails go to Gmail's Trash once
   they're 2 hours old (Gmail empties Trash after 30 days). Other emails stay
   where they are. To also sort emails read on earlier runs, run once with
   `--sort-old`. FRIDAY never sends mail.

## Outreach tracking (cold emails to recruiters and alumni)

If you send cold emails yourself, for example with the Mailer
(`send_recruiters.py`), FRIDAY can keep track of them. It never sends or
drafts anything: it only reads what you already sent.

1. Pick a Gmail search that finds exactly those emails in your Sent mail. The
   subject line from your template usually does it. Try it in Gmail's search
   box first, then put it in `.env`:
   ```
   OUTREACH_QUERY=in:sent newer_than:90d subject:"Software / ML Engineer interested in"
   ```
   That's the subject the Mailer uses ("MS CS @ ASU – Software / ML Engineer
   interested in {company}"), and FRIDAY reads the company from the end of it.
   Change the search if you change the template.
2. Run FRIDAY as usual. Each run logs new matches in an **Outreach** tab (or
   `outreach.csv`) and reads every email's thread again to set its status:
   - **Waiting**: sent, no answer yet.
   - **Follow-up due**: no answer after `FOLLOW_UP_DAYS` (default 7). Reply in
     the same thread once; FRIDAY sees it and moves the row to **Followed up**.
   - **No reply**: still nothing `FOLLOW_UP_DAYS` after your follow-up. Let it go.
   - **Replied**: they wrote back, in the thread or in a new email from the same
     address. Out-of-office replies don't count.
   - **Bounced**: the address doesn't exist.

   Scheduled runs notify you about new replies, bounces and follow-ups due.
3. In the dashboard, the **Outreach** tab shows who to follow up with, your
   reply rate, and the full list. You can fix names and companies, add notes,
   and mark a row Replied by hand (for example after a LinkedIn reply); Replied
   and Bounced rows are never changed by later runs.

It uses the same Gmail access FRIDAY already has, so there's no new login. The
Mailer needs no changes. Run with `--no-outreach` to skip it for one run.

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

The login creates `token.json`. If you logged in before FRIDAY moved emails
into folders, it asks you to log in once more to allow that. Keep it and `credentials.json` private (both
are in `.gitignore`).

## Everyday use (Mac)

- **Double-click `FRIDAY.command`** in Finder. It checks your email for new
  job updates, then opens the dashboard in your browser. Close the Terminal
  window when you're done.
- **Automatic checks:** run `./scripts/schedule_mac.sh` once. Your Mac then
  checks every 3 hours while it's awake and shows a notification when an
  application changes. Turn it off with `./scripts/schedule_mac.sh off`.
- Google logs this app out about once a week while it's in "Testing" mode.
  When that happens you'll get a "FRIDAY needs you" notification; double-click
  `FRIDAY.command` and log in again.

## Open new job postings for Tsenta

`tracker/open_jobs.py` reads the Software Engineering section of the
[SimplifyJobs New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions#-software-engineering-new-grad-roles)
list and opens each open role's apply link in a browser tab, a batch at a
time, so Tsenta can apply. Closed roles (🔒) are skipped, and every link it
opens is logged in `opened_jobs.csv`, so a role never opens twice. Run it
whenever the list updates and you only get what's new.

Double-click **`OpenJobs.command`** in Finder, or from Terminal:

```bash
python3 -m tracker.open_jobs                      # 10 tabs, then waits for Enter before the next 10
python3 -m tracker.open_jobs --list               # just show what would open
python3 -m tracker.open_jobs --batch 15 --browser "Google Chrome"
python3 -m tracker.open_jobs --max-age 14 --location Remote --location AZ
python3 -m tracker.open_jobs --skip-no-sponsor --skip-citizen
python3 -m tracker.open_jobs --mark-seen          # log everything current as seen, open nothing
python3 -m tracker.open_jobs --browser "Google Chrome" --wait 120 --close
                                                  # every 2 minutes, close the tabs and open the next 10
```

With `--close`, each batch opens in its own Chrome window, which is closed
before the next batch opens. The first time, macOS asks whether Terminal may
control Chrome: click OK. Press Ctrl+C during the countdown to stop and leave
the current tabs open.

**Automatic:** run `./scripts/schedule_jobs_mac.sh` once. Your Mac then opens
new postings on its own every 3 hours while it's awake (Chrome, 10 at a time,
2 minutes per batch, last 3 days). Turn it off with
`./scripts/schedule_jobs_mac.sh off`. Log: `logs/open_jobs.log`.

It needs no setup beyond Python 3. Change the double-click defaults by
editing the `OPTIONS=` line at the top of `OpenJobs.command`.

## Dashboard

```bash
streamlit run dashboard.py
```

Opens in your browser. The **Today** view is a calm overview:

- **Active pipeline**: open applications by stage. Click a row's arrow to add
  interview rounds (time, interviewer, meeting link, prep doc), set the work
  mode, and keep notes.
- **Next 48 hours**: upcoming rounds with one-click meeting and prep links.
- **Funnel**: how many reached each stage and the conversion between them.
- **Follow-up queue**: next steps the tracker found plus your own to-dos
  (saved in `todos.csv`, or a "To-dos" tab in your Sheet).

Use **Add application** for jobs you applied to outside email, the Remote /
Hybrid / Onsite pills to filter, and the mail button to check email right away.
Other tabs: an editable table of everything, your cold-email outreach (see
above), each company's email history, and the full email log.

Set `SEARCH_TITLE` in `.env` to change the heading. To try it with sample data
(no Gmail needed): `streamlit run dashboard.py -- --demo`.

## Tests

```bash
python -m unittest discover -s tests -t .
```

`tests/test_job_emails.py` holds real subject lines and previews. When the
rules get an email wrong, add it there and adjust `tracker/job_emails.py`.
