"""Open new-grad Software Engineering job postings in browser tabs, a batch at a time.

Reads the SimplifyJobs New-Grad-Positions list, skips closed roles and any
link you've already opened (kept in opened_jobs.csv), and opens the apply
links so Tsenta AI can apply on each tab.

    python -m tracker.open_jobs                 # 10 tabs per batch, default browser
    python -m tracker.open_jobs --batch 15 --browser "Google Chrome"
    python -m tracker.open_jobs --list          # just show what would open
    python -m tracker.open_jobs --browser "Google Chrome" --wait 120 --close
                                                # every 2 minutes, close the tabs and open the next batch
"""

import argparse
import csv
import html
import os
import re
import subprocess
import sys
import time
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

README_URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
SECTION = "Software Engineering New Grad Roles"
# Short names for --section.
SECTIONS = {
    "swe": SECTION,
    "ai": "Data Science, AI & Machine Learning New Grad Roles",
    "pm": "Product Management New Grad Roles",
    "quant": "Quantitative Finance New Grad Roles",
    "hardware": "Hardware Engineering New Grad Roles",
}
LOG_FILE = "opened_jobs.csv"
LOG_FIELDS = ["Opened", "Company", "Role", "Location", "Age", "URL"]

NO_SPONSOR = "\U0001f6c2"  # 🛂
US_CITIZEN = "\U0001f1fa\U0001f1f8"  # 🇺🇸
CLOSED = "\U0001f512"  # 🔒
# Browsers whose windows AppleScript can open and close, which --close needs.
SCRIPTABLE_BROWSERS = {"Google Chrome", "Brave Browser", "Microsoft Edge", "Chromium"}
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "ref", "gh_src"}


@dataclass
class Job:
    company: str
    role: str
    location: str
    url: str
    age: str

    @property
    def age_days(self):
        m = re.match(r"(\d+)\s*(d|mo)", self.age)
        if not m:
            return 0
        return int(m.group(1)) * (30 if m.group(2) == "mo" else 1)

    @property
    def flags(self):
        return self.company + " " + self.role


def fetch_readme(url=README_URL):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _text(cell):
    cell = re.sub(r"<summary>.*?</summary>", "", cell, flags=re.S)
    cell = re.sub(r"</?br\s*/?>", " / ", cell)
    return html.unescape(re.sub(r"<[^>]+>", "", cell)).strip(" /")


def parse_jobs(readme, section=SECTION):
    """Active roles in one section of the README, newest first, closed ones left out."""
    start = readme.find(section)
    if start < 0:
        raise ValueError(f"Couldn't find the '{section}' section in the README")
    end = readme.find("\n## ", start)
    body = readme[start:end if end > 0 else None]
    # The first table is the active roles; the inactive ones sit in a <details> after it.
    m = re.search(r"<tbody>(.*?)</tbody>", body, re.S)
    if not m:
        return []
    jobs, company = [], ""
    for row in re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S):
        cells = re.findall(r"<td>(.*?)</td>", row, re.S)
        if len(cells) < 5:
            continue
        name = _text(cells[0])
        if name and name != "↳":
            company = name
        if CLOSED in cells[3]:
            continue
        link = re.search(r'<a href="([^"]+)"[^>]*>\s*<img[^>]*alt="Apply"', cells[3])
        if not link:
            continue
        jobs.append(Job(company, _text(cells[1]), _text(cells[2]), html.unescape(link.group(1)), _text(cells[4])))
    return jobs


def normalize(url):
    """The same posting with tracking params stripped, so re-tagged links still match the log."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS]
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def load_opened(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {normalize(row["URL"]) for row in csv.DictReader(f) if row.get("URL")}


def log_opened(path, jobs):
    new_file = not os.path.exists(path)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            writer.writeheader()
        for job in jobs:
            writer.writerow({"Opened": stamp, "Company": job.company, "Role": job.role,
                             "Location": job.location, "Age": job.age, "URL": job.url})


# Places outside the US, for --us-only. A role listed in several places is kept if any of them is in the US.
_ABROAD = re.compile(
    r"\b(?:UK|U\.K\.|United Kingdom|England|Scotland|London|Cambridge, UK|Canada|Toronto|Vancouver|Montreal|Ottawa|"
    r"Waterloo, ON|Ontario|ON|BC|QC|AB|India|Bangalore|Bengaluru|Hyderabad|Pune|Mumbai|Delhi|Gurgaon|Gurugram|Noida|"
    r"Chennai|Germany|Berlin|Munich|Ireland|Dublin|France|Paris|Netherlands|Amsterdam|Singapore|Japan|Tokyo|"
    r"Australia|Sydney|Melbourne|Israel|Tel Aviv|Poland|Warsaw|Spain|Madrid|Barcelona|Mexico|Brazil|China|Taiwan|"
    r"Korea|Seoul|Switzerland|Zurich|Sweden|Stockholm|Denmark|Copenhagen|Portugal|Lisbon|Romania|Czechia|Prague|"
    r"Philippines|Vietnam|Hong Kong|UAE|Dubai)\b"
)


def in_us(location: str) -> bool:
    places = [p for p in re.split(r"\s*(?:/|;|\||<br\s*/?>|\n)\s*", location) if p.strip()]
    return not places or any(not _ABROAD.search(p) for p in places)


def select(jobs, opened=(), max_age=None, locations=(), skip_no_sponsor=False, skip_citizen=False, us_only=False):
    picked, seen = [], set(opened)
    for job in jobs:
        key = normalize(job.url)
        if key in seen:
            continue
        if max_age is not None and job.age_days > max_age:
            continue
        if locations and not any(loc.lower() in job.location.lower() for loc in locations):
            continue
        if skip_no_sponsor and NO_SPONSOR in job.flags:
            continue
        if skip_citizen and US_CITIZEN in job.flags:
            continue
        if us_only and not in_us(job.location):
            continue
        seen.add(key)
        picked.append(job)
    return picked


def open_tab(url, browser=None):
    if sys.platform == "darwin":
        cmd = ["open", "-a", browser, url] if browser else ["open", url]
        subprocess.run(cmd, check=False)
    else:
        webbrowser.open_new_tab(url)


def _osascript(script):
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def open_window(urls, browser):
    """Open the urls as tabs in a new browser window and return the window's id (None if it failed)."""
    lines = [f"tell application {_quote(browser)}", "set w to make new window",
             f"set URL of active tab of w to {_quote(urls[0])}"]
    lines += [f"tell w to make new tab with properties {{URL:{_quote(url)}}}" for url in urls[1:]]
    lines += ["return id of w", "end tell"]
    return _osascript("\n".join(lines))


def close_window(window_id, browser):
    _osascript(f"tell application {_quote(browser)} to close (every window whose id is {window_id})")


def countdown(seconds, message):
    """Wait, showing the time left. False if you pressed Ctrl+C to stop."""
    try:
        if not sys.stdout.isatty():  # running in the background: no live timer in the log
            print(f"{message} in {seconds}s")
            time.sleep(seconds)
            return True
        for left in range(seconds, 0, -1):
            print(f"\r{message} in {left // 60}:{left % 60:02d} (Ctrl+C to stop) ", end="", flush=True)
            time.sleep(1)
        print()
        return True
    except KeyboardInterrupt:
        print()
        return False


def describe(job):
    return f"{job.company} | {job.role} | {job.location} | {job.age}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--batch", type=int, default=10, help="tabs to open at a time (default 10)")
    p.add_argument("--browser", help='Mac app to open tabs in, e.g. "Google Chrome" (default: your default browser)')
    p.add_argument("--max-age", type=int, metavar="DAYS", help="only roles posted in the last DAYS days")
    p.add_argument("--location", action="append", default=[], metavar="TEXT",
                   help="only roles whose location contains TEXT (repeat for several, e.g. --location Remote --location AZ)")
    p.add_argument("--skip-no-sponsor", action="store_true", help="skip roles marked as not offering sponsorship")
    p.add_argument("--skip-citizen", action="store_true", help="skip roles that require U.S. citizenship")
    p.add_argument("--us-only", action="store_true", help="skip roles located only outside the US")
    p.add_argument("--list", action="store_true", help="show what would open, without opening or logging anything")
    p.add_argument("--mark-seen", action="store_true", help="log every matching role as opened without opening it")
    p.add_argument("--no-prompt", action="store_true", help="open every batch without waiting for Enter")
    p.add_argument("--wait", type=int, metavar="SECONDS",
                   help="open the next batch after SECONDS instead of waiting for Enter")
    p.add_argument("--close", action="store_true",
                   help="close each batch's tabs before opening the next (Mac, with --browser set to Chrome, Brave or Edge)")
    p.add_argument("--section", action="append", choices=sorted(SECTIONS), metavar="NAME",
                   help="which part of the list to read: " + ", ".join(sorted(SECTIONS)) +
                        " (repeat for several; default swe)")
    p.add_argument("--readme", help="read the list from a local file instead of GitHub")
    p.add_argument("--log", default=LOG_FILE, help=f"where to keep the opened-links log (default {LOG_FILE})")
    args = p.parse_args(argv)

    if args.readme:
        with open(args.readme, encoding="utf-8") as f:
            readme = f.read()
    else:
        print("Fetching the latest list from GitHub...")
        readme = fetch_readme()
    listed = [job for name in (args.section or ["swe"]) for job in parse_jobs(readme, SECTIONS[name])]
    jobs = select(listed, load_opened(args.log), args.max_age, args.location,
                  args.skip_no_sponsor, args.skip_citizen, args.us_only)
    print(f"{len(jobs)} new open role(s) to go through.")
    if not jobs:
        return 0

    if args.list:
        for job in jobs:
            print(f"  {describe(job)}\n    {job.url}")
        return 0
    if args.mark_seen:
        log_opened(args.log, jobs)
        print(f"Logged {len(jobs)} role(s) in {args.log}; they won't open next time.")
        return 0

    closing = args.close and sys.platform == "darwin" and args.browser in SCRIPTABLE_BROWSERS
    if args.close and not closing:
        print(f"--close only works on a Mac with --browser set to one of: {', '.join(sorted(SCRIPTABLE_BROWSERS))}. "
              "Tabs will stay open.")
    batch = max(1, args.batch)
    for i in range(0, len(jobs), batch):
        chunk = jobs[i:i + batch]
        last = i + batch >= len(jobs)
        print(f"\nOpening {i + 1}-{i + len(chunk)} of {len(jobs)}:")
        for job in chunk:
            print(f"  {describe(job)}")
        window = open_window([job.url for job in chunk], args.browser) if closing else None
        if closing and not window:
            print("Couldn't control the browser (allow Terminal under System Settings > Privacy & Security > "
                  "Automation). Opening tabs without closing them.")
            closing = False
        if not window:
            for job in chunk:
                open_tab(job.url, args.browser)
                time.sleep(0.4)
        log_opened(args.log, chunk)
        if last and not window:
            break
        if args.wait:
            keep_going = countdown(args.wait, "Closing these tabs" if last else
                                   "Closing these tabs and opening the next batch" if window else "Next batch")
        elif args.no_prompt:
            keep_going = True
        else:
            prompt = "close these tabs" if last else "open the next batch"
            answer = input(f"\nPress Enter once Tsenta is done with these to {prompt} (q to stop): ")
            keep_going = not answer.strip().lower().startswith("q")
        if not keep_going:
            break
        if window:
            close_window(window, args.browser)
        if last:
            break
    print(f"\nDone. Opened links are logged in {args.log}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
