# F.R.I.D.A.Y.

A personal assistant for a job search and a semester, running on your Mac. FRIDAY reads your
Gmail accounts, Canvas, calendars and your other projects, keeps a tracker of every job
application, and tells you on your phone what needs you: a good-morning message with the day's
list, and an alert 30 minutes before anything is due or starts.

It reads; it never sends email or applies to anything on its own.

```
Good morning, Naman ☀️ It's Saturday, 31 October.

"The secret of getting ahead is getting started." — Mark Twain

🟠 Tomorrow
• CSE 540: Submission: Draft Smart Contract Design (due tomorrow)
• CSE 579: Assignment 2: Simple Answer Set Programming (due tomorrow)

📌 To do
• Complete the assessment at Rokt

✉️ Reply to
• Samina Tushi: Re: Software and AI roles at Kodiak (waiting 5 days)

📈 Stocks
• Momentum ₹34.88 L (−0.3%) · Nifty 50 +1.3% since 26 Oct
• Last 24h: Momentum: SELL Illumina, Inc. (ILMN)

I'll keep you posted on everything else. Just lock in. 💪
```

## What it does

| Feature | What you get | Runs |
|---|---|---|
| **Job application tracker** | Every application with its status (Applied, Assessment, Interview, Offer, Rejected), read from company emails in all your Gmail accounts | Every 3 hours |
| **Gmail folders** | Job emails moved to *USA Jobs* and *USA Jobs/Actions to be Taken*; security codes binned after 2 hours | With each check |
| **Cold-email outreach** | Who replied, who bounced, who's due a follow-up | With each check |
| **Morning message** | Greeting, a quote, then today, tomorrow, to-dos, emails waiting on your reply, later this week and your stock app | 8:00 (and a list at 18:00) |
| **Deadline alerts** | A phone alert 30 minutes before a Canvas deadline, class, call or interview | Checked every 5 minutes |
| **Important-news alerts** | Interview or assessment invites, offers, recruiter replies (not every "thanks for applying") | With each check |
| **Dashboard** | Pipeline, funnel, interview rounds, to-dos, outreach, company history | `FRIDAY.command` |
| **Job opener** | New-grad postings from the SimplifyJobs list opened in Chrome for the Tsenta extension to apply | Optional, every 3 hours |

## Setup

You need a Mac, Python 3 and about 15 minutes.

```bash
git clone https://github.com/mananbatraa/FRIDAY.git && cd FRIDAY
./setup.sh
```

`setup.sh` walks you through everything and is safe to run again; it skips what's done:

1. Installs FRIDAY's packages in `.venv`.
2. Creates your `.env` settings and asks what to call you.
3. Logs in to Gmail (and any other Gmail you add).
4. Connects Canvas, your calendars and the stock app, if you paste their links.
5. Sets up phone notifications with ntfy and sends a test.
6. Runs a first email check.
7. Asks, one by one, which background jobs to turn on.

`./setup.sh --status` shows what's set up and what's running, without changing anything.

### The one manual step: a Google Cloud app

Google requires an "app" for any program that reads Gmail. You make one once:

1. Go to <https://console.cloud.google.com/> and create a project (e.g. "FRIDAY").
2. **APIs & Services → Library**: enable the **Gmail API** (and the **Google Sheets API** if
   you want a Sheet instead of CSV files).
3. **Google Auth Platform → Audience**: choose *External*. Then either add each Gmail you'll
   use as a **test user**, or click **Publish app**. Publishing is better: in Testing mode
   Google logs you out every 7 days. A published personal app shows an "unverified app"
   warning once at login; click *Advanced → Go to …*.
4. **Clients → Create client → Desktop app**, download the JSON, and save it in the FRIDAY
   folder as `credentials.json`.

Then run `./setup.sh` again.

*Several Gmail accounts:* set `ALSO_READ_GMAIL=you@university.edu`. If that account can't
use your app (e.g. a university Workspace that only allows approved apps), put another app's
file in the folder as `credentials_<name>.json` (for `you@university.edu`,
`credentials_you.json`) and that account logs in through it.

## Phone notifications

**ntfy (recommended, free).** Install the *ntfy* app, allow notifications, tap **+** and
subscribe to the topic `setup.sh` gives you (`NTFY_TOPIC` in `.env`). Morning messages,
deadline alerts and important news all arrive as normal notifications. Keep the topic
private: anyone who knows it can read your alerts.

Other options for the morning message, if set (the first one wins):

- **WhatsApp** through the free [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/):
  save their number, send it "I allow callmebot to send me messages", and put your number and
  the key it replies with in `WHATSAPP_PHONE` and `CALLMEBOT_APIKEY`. CallMeBot sees each
  message, and its bot is sometimes full; try again in a few days.
- **Telegram**: create a bot with @BotFather and set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- **iMessage** from this Mac (`REMINDER_PHONE`). Sent to your own number, it arrives without an alert.

## Connecting your day

Set these in `.env` (or let `setup.sh` ask). Each link is private: treat it like a password.

| Source | Where to find it | Setting |
|---|---|---|
| **Canvas** assignments, quizzes and classes | Canvas → Calendar → **Calendar Feed** (bottom right) | `CANVAS_ICS_URL` |
| **Calendars** (calls, meetings, interviews) | Google Calendar → ⚙️ Settings → your calendar → Integrate calendar → **Secret address in iCal format** | `CALENDAR_ICS_URLS` (comma-separated) |
| **Stock app** | The `stock-research` folder | `STOCKS_DIR` |
| **Cold emails** you send | A Gmail search for them in your Sent mail | `OUTREACH_QUERY` |

Canvas items with only a date are due at 11:59 PM, as on Canvas. Calendar times are converted
to your Mac's time zone, and repeating events (weekly calls) are filled in.

## Everyday use

| You want to… | Do this |
|---|---|
| Check email now and open the dashboard | Double-click **`FRIDAY.command`** |
| See tomorrow's morning message | `.venv/bin/python -m tracker.reminder --print` |
| See the next 7 days | `.venv/bin/python -m tracker.deadlines --list` |
| Stop reminders for something you finished | `.venv/bin/python -m tracker.deadlines --done "smart contract"` |
| Mark a to-do done | Tick it on the dashboard, or set its *Done* date in `todos.csv` |
| Re-read every job email (after a rules change) | `.venv/bin/python -m tracker.main --rebuild --days 45` (back up `applications.csv` first) |
| See what's set up and running | `./setup.sh --status` |

### Background jobs

Each runs while your Mac is awake (a missed run happens when it wakes). Turn one on by running
its script, off with `off`:

| Job | Script | Log |
|---|---|---|
| Email check every 3 hours | `./scripts/schedule_mac.sh` | `logs/tracker.log` |
| Morning message 8:00, list 18:00 | `./scripts/remind_mac.sh 8:00 18:00` | `logs/reminder.log` |
| Deadline alerts (every 5 minutes) | `./scripts/alerts_mac.sh` | `logs/alerts.log` |
| Job opener every 3 hours | `./scripts/schedule_jobs_mac.sh` | `logs/open_jobs.log` |

If a Google login expires you get a "FRIDAY needs you" notification: double-click
`FRIDAY.command` and log in again.

## How it works

### Reading job emails

1. Searches each Gmail for job-related emails from the last `DAYS` days.
2. Sorts each new email into **Applied**, **Assessment**, **Interview**, **Offer**,
   **Rejected**, **Verification** (codes, identity checks) or **Other**, and finds the company
   and role. Built-in rules do this (`tracker/job_emails.py`); with `ANTHROPIC_API_KEY` set,
   Claude reads each email instead, with the rules as a fallback.
   - The rules clean up names ("MyWorkday T-Mobile" → "T-Mobile", "Navy Federal Credit Union
     has been received" → "Navy Federal Credit Union"), strip requisition numbers from roles,
     read the real sender from Tsenta-forwarded mail and merge spellings of one company.
   - They read deadlines ("within 5 days", "by November 3") and next steps ("Reply with your
     availability") into the *Next action* column.
3. Updates the **Applications** table: one row per company and role. Status only moves forward
   (Applied → Assessment → Interview → Offer); Rejected can come at any stage, and a "thanks
   for applying" on the same day as a rejection doesn't reopen it. Your Notes are never touched.
4. Logs every processed email in the **Emails** table, so nothing is counted twice.
5. Moves job emails into **USA Jobs** and **USA Jobs/Actions to be Taken** in the mailbox they
   came from; security-code emails go to Trash once they're 2 hours old.

Without a Google Sheet (`SHEET_ID`), the tables are `applications.csv`, `emails.csv`,
`todos.csv` and `outreach.csv`.

### Outreach tracking

Set `OUTREACH_QUERY` to a Gmail search that finds the cold emails you sent, e.g.
`in:sent newer_than:90d (subject:"MS CS student interested in" OR subject:"roles at")`.
Each run logs new ones and sets each email's status: **Waiting**, **Follow-up due** (no answer
after `FOLLOW_UP_DAYS`), **Followed up**, **No reply**, **Replied** (out-of-office replies
don't count) or **Bounced**. The company is read from the end of the subject.

### The morning message and alerts

`tracker/reminder.py` builds the message from FRIDAY's tables plus `tracker/daily.py` (emails
waiting on your reply, from people rather than systems or mailing lists, grouped by person; the
stock app's performance, last-24-hour trades, ₹1L account changes and queued orders) and
`tracker/deadlines.py` (everything with a time on it). The quote rotates daily
(`tracker/quotes.py`). Before noon it's the morning format; later it's a plain list.

`tracker/deadlines.py` runs every 5 minutes and sends one alert per item, 30 minutes before.
Items you mark done (`--done`) are kept in `done.json` and never come up again.

## Dashboard

```bash
.venv/bin/streamlit run dashboard.py      # or double-click FRIDAY.command
```

- **Today**: active pipeline by stage (click a row to add interview rounds, work mode, notes),
  the next 48 hours, the funnel, and the follow-up queue with your to-dos.
- **All applications**: an editable table; change Stage, Work mode, Next action or Notes and
  press Save.
- **Outreach**: who to follow up with, your reply rate, the full list.
- **Company history** and the full **Email log**.

Try it with sample data, no Gmail needed: `.venv/bin/streamlit run dashboard.py -- --demo`.

## Job opener (for Tsenta)

`tracker/open_jobs.py` reads the [SimplifyJobs New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions)
list and opens each open role's apply link in Chrome, a batch at a time. With Tsenta's Chrome
extension installed and *Apply when I open a job* on, Tsenta applies on each tab. Every link
opened is logged in `opened_jobs.csv`, so a role never opens twice.

```bash
.venv/bin/python -m tracker.open_jobs --list                          # show what would open
.venv/bin/python -m tracker.open_jobs --section swe --section ai \
    --skip-citizen --us-only --browser "Google Chrome" --wait 120 --close
```

| Option | Does |
|---|---|
| `--section swe` / `ai` / `pm` / `quant` / `hardware` | Which part of the list (repeatable; default `swe`) |
| `--max-age DAYS` | Only roles posted in the last DAYS days |
| `--skip-no-sponsor`, `--skip-citizen` | Skip roles that don't sponsor visas or need US citizenship |
| `--us-only` | Skip roles located only outside the US |
| `--location TEXT` | Only roles whose location contains TEXT (repeatable) |
| `--batch N`, `--wait SECONDS`, `--close` | N tabs at a time; next batch after SECONDS; close the last batch first |
| `--mark-seen` | Log everything current as opened without opening it |

The schedule (`./scripts/schedule_jobs_mac.sh`) opens new postings from the last 3 days every
3 hours with the visa and US filters on. Without the Tsenta extension it only opens tabs, so
leave it off. Double-click **`OpenJobs.command`** for a one-off run.

## Privacy

Everything stays on your Mac. These files hold logins, private links or your data and are
never committed (see `.gitignore`): `.env`, `credentials*.json`, `token*.json`, the `*.csv`
tables, `done.json`, `logs/` and `backups/`. Don't share them. To disconnect FRIDAY from a
Google account, remove it at <https://myaccount.google.com/permissions>.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Access blocked: … has not completed the Google verification process" | Add that Gmail as a test user in your Google Cloud app, or publish the app (setup step 3) |
| "FRIDAY needs you: Google login expired" | Double-click `FRIDAY.command` and log in. Publish the app to stop weekly expiry. |
| No phone notifications | ntfy app: notifications allowed and subscribed to exactly your `NTFY_TOPIC` |
| A background job isn't running | `./setup.sh --status`; read its log in `logs/`; run its script again |
| An email got the wrong status or company | Add it to `tests/test_job_emails.py`, adjust `tracker/job_emails.py`, then `--rebuild` |
| Something you finished keeps coming up | `python -m tracker.deadlines --done "<part of its name>"` |

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -t .
```

The tests use real email subjects and calendar entries (with personal details removed). When a
rule gets something wrong, add the case there first, then fix the rule.

## Project layout

```
setup.sh                  guided setup and --status
FRIDAY.command            double-click: check email, open the dashboard
OpenJobs.command          double-click: open new postings for Tsenta
dashboard.py              Streamlit dashboard
tracker/
  main.py                 the email check (all accounts), Gmail folders, outreach
  job_emails.py           rules: kind, company, role, deadlines, next steps
  tracker.py              how an email changes an application row
  outreach.py             cold-email tracking
  reminder.py             morning message and evening list, and where they're sent
  daily.py                emails waiting on your reply, stock app summary
  deadlines.py            Canvas, calendars, interviews, dated to-dos; 30-minute alerts
  quotes.py               the morning quote
  notify.py               Mac and ntfy notifications
  open_jobs.py            job opener
  gmail_client.py, google_auth.py, config.py, storage.py, models.py, llm.py, folders.py
scripts/                  background job switches (launchd)
tests/                    unit tests
```
