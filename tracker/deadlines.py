"""Everything with a time on it, in one list: Canvas work, calendar calls, interview rounds and dated to-dos.

    python -m tracker.deadlines            # send alerts for anything starting or due in the next 30 minutes
    python -m tracker.deadlines --list     # show the next 7 days
    python -m tracker.deadlines --done "smart contract"   # mark matching items done (no more reminders)

The morning report's "Today" and "This week" sections come from here too. Run
./scripts/alerts_mac.sh once to check every 5 minutes in the background.

Sources (set in .env; any that aren't set are skipped):
- CANVAS_ICS_URL: Canvas > Calendar > "Calendar Feed".
- CALENDAR_ICS_URLS: comma-separated private iCal links, e.g. Google Calendar > Settings >
  your calendar > "Secret address in iCal format". This is how scheduled calls get in.
- Interview rounds and dated to-dos: FRIDAY's own tables.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .daily import _COURSE, _NOT_WORK, _ics_when, _unfold

ALERT_BEFORE = timedelta(minutes=30)
DONE_FILE = "done.json"  # keys of items you've finished
SENT_FILE = "logs/alerts_sent.json"  # keys already alerted, so nothing is sent twice
END_OF_DAY = (23, 59)  # an all-day due date means due by 11:59 PM, as on Canvas


@dataclass(frozen=True)
class Item:
    when: datetime
    title: str
    kind: str  # "due" (hand something in) or "event" (be somewhere: a call, an interview)
    all_day: bool = False
    source: str = ""

    @property
    def key(self) -> str:
        return f"{self.kind}|{self.title}|{self.when:%Y-%m-%d}"

    def label(self, today: date) -> str:
        day = "today" if self.when.date() == today else \
            "tomorrow" if self.when.date() == today + timedelta(days=1) else self.when.strftime("%a %b %-d")
        if self.kind == "due":
            time = "" if self.all_day else f" {self.when:%-I:%M %p}"
            return f"{self.title} (due {day}{time})"
        return f"{self.title} ({day}" + ("" if self.all_day else f" {self.when:%-I:%M %p}") + ")"


# ---------------------------------------------------------------- sources


_DAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
REPEAT_AHEAD = timedelta(days=21)  # how far ahead repeating events are filled in


def _start(value: str, tzid: str) -> datetime | None:
    """An event start in this Mac's local time, honouring TZID=America/Chicago-style tags."""
    when = _ics_when(value)
    if when and tzid and len(value.strip()) > 8 and not value.strip().endswith("Z"):
        try:
            when = when.replace(tzinfo=ZoneInfo(tzid)).astimezone().replace(tzinfo=None)
        except (KeyError, ValueError):
            pass
    return when


def _repeats(first: datetime, rule: str, skip: set, now: datetime) -> list[datetime]:
    """Occurrences of a DAILY or WEEKLY repeating event from a day ago to REPEAT_AHEAD ahead."""
    parts = dict(p.split("=", 1) for p in rule.split(";") if "=" in p)
    freq, step = parts.get("FREQ"), int(parts.get("INTERVAL", "1") or 1)
    if freq not in ("DAILY", "WEEKLY"):
        return [first]  # monthly/yearly: just the first one
    until = _ics_when(parts["UNTIL"]) if parts.get("UNTIL") else None
    count = int(parts["COUNT"]) if parts.get("COUNT") else None
    days = {_DAYS[d[-2:]] for d in parts.get("BYDAY", "").split(",") if d[-2:] in _DAYS} or {first.weekday()}
    out, n, day = [], 0, first
    end = now + REPEAT_AHEAD
    while day <= end and (until is None or day <= until) and (count is None or n < count):
        weeks = (day.date() - first.date()).days // 7
        if freq == "DAILY" or (day.weekday() in days and weeks % step == 0):
            if freq == "DAILY" and (day.date() - first.date()).days % step:
                day += timedelta(days=1)
                continue
            n += 1
            if day >= now - timedelta(days=1) and day not in skip:
                out.append(day)
        day += timedelta(days=1)
    return out


def parse_events(ics: str, now: datetime | None = None) -> list[tuple[datetime, str, bool]]:
    """(start, title, all-day) for every event in an iCalendar feed, repeating ones filled in."""
    now = now or datetime.now()
    events, current = [], None
    for line in _unfold(ics):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            start = current.get("DTSTART", "")
            when = _start(start, current.get("DTSTART_TZID", ""))
            if when and current.get("SUMMARY") and current.get("STATUS", "").upper() != "CANCELLED":
                all_day = len(start.strip()) == 8
                skip = {_start(x, current.get("EXDATE_TZID", "")) for x in current.get("EXDATE", "").split(",") if x}
                starts = _repeats(when, current["RRULE"], skip, now) if current.get("RRULE") else [when]
                events += [(w, current["SUMMARY"], all_day) for w in starts]
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            name, *params = key.split(";")
            for param in params:
                if param.startswith("TZID="):
                    current[f"{name}_TZID"] = param[5:]
            current[name] = value.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ")
    return events


def canvas_items(ics: str) -> list[Item]:
    items = []
    for when, title, all_day in parse_events(ics):
        if re.search(r"office hours?", title, re.IGNORECASE):
            continue
        course = _COURSE.search(title)
        if course:
            code = f"{course.group(1)} {course.group(2)}"
            title = _COURSE.sub("", title).strip()
            # "CSE 540: Engr Blockchain Applications (2026 Fall B) Instructor led live session" -> "CSE 540: live session"
            title = re.sub(rf"^{code}:?\s*.*?\(\d{{4}} [^)]*\)\s*-?\s*", "", title)
            title = f"{code}: {title}"
        if _NOT_WORK.search(title):  # a live class session: somewhere to be, not work to hand in
            items.append(Item(when, title, "event", all_day, "Canvas"))
        else:
            due = when.replace(hour=END_OF_DAY[0], minute=END_OF_DAY[1]) if all_day else when
            items.append(Item(due, title, "due", all_day, "Canvas"))
    return items


def calendar_items(ics: str) -> list[Item]:
    return [Item(when, title, "event", all_day, "Calendar") for when, title, all_day in parse_events(ics)]


def table_items(apps: list[dict], todos: list[dict]) -> list[Item]:
    """Interview rounds from the Applications table and dated to-dos."""
    items = []
    for row in apps:
        if row.get("Status") == "Rejected":
            continue
        try:
            rounds = json.loads(row.get("Rounds") or "[]")
        except ValueError:
            continue
        for r in rounds if isinstance(rounds, list) else []:
            try:
                when = datetime.fromisoformat(r.get("When", ""))
            except (AttributeError, TypeError, ValueError):
                continue
            items.append(Item(when, f"{r.get('Round') or 'Interview'} with {row.get('Company', '')}", "event"))
    for t in todos:
        if t.get("Done"):
            continue
        try:
            due = date.fromisoformat(str(t.get("Due", "")).strip()[:10])
        except ValueError:
            continue
        items.append(Item(datetime.combine(due, datetime.min.time()).replace(hour=END_OF_DAY[0], minute=END_OF_DAY[1]),
                          t.get("Task", ""), "due", True, "To-do"))
    return items


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def collect(apps: list[dict] | None = None, todos: list[dict] | None = None) -> tuple[list[Item], list[str]]:
    """Every dated item from every source, minus the ones marked done, and any source errors."""
    items, problems = [], []
    canvas = os.environ.get("CANVAS_ICS_URL", "").strip()
    if canvas:
        try:
            items += canvas_items(_fetch(canvas))
        except OSError:
            problems.append("Couldn't reach the Canvas calendar feed")
    for url in [u.strip() for u in os.environ.get("CALENDAR_ICS_URLS", "").split(",") if u.strip()]:
        try:
            items += calendar_items(_fetch(url))
        except OSError:
            problems.append("Couldn't reach one of your calendars")
    items += table_items(apps or [], todos or [])
    done = load_done()
    unique = {i.key: i for i in items if i.key not in done}
    return sorted(unique.values(), key=lambda i: i.when), problems


# ---------------------------------------------------------------- done and sent


def _load(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def _save(path: str, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1))


def load_done() -> dict:
    return _load(DONE_FILE)


def mark_done(items: list[Item], text: str, today: date) -> list[Item]:
    """Mark every upcoming item whose title contains `text` as done."""
    matches = [i for i in items if text.lower() in i.title.lower() and i.when.date() >= today - timedelta(days=1)]
    done = load_done()
    for i in matches:
        done[i.key] = today.isoformat()
    _save(DONE_FILE, done)
    return matches


def due_for_alert(items: list[Item], now: datetime, sent: dict) -> list[Item]:
    """Items starting or due within ALERT_BEFORE that haven't been alerted yet (all-day events get none)."""
    return [i for i in items if not (i.kind == "event" and i.all_day)
            and now < i.when <= now + ALERT_BEFORE and i.key not in sent]


def alert_text(item: Item, now: datetime) -> str:
    minutes = max(1, round((item.when - now).total_seconds() / 60))
    verb = "due" if item.kind == "due" else "starts"
    return f"{item.title}: {verb} in {minutes} min ({item.when:%-I:%M %p})"


# ---------------------------------------------------------------- report sections


def report_sections(items: list[Item], now: datetime) -> list[tuple[str, list[str]]]:
    today = now.date()
    todays = [i.label(today) for i in items if i.when.date() == today and i.when >= now - timedelta(hours=1)]
    tomorrow = today + timedelta(days=1)
    next_day = [i.label(today) for i in items if i.when.date() == tomorrow]
    week = [i.label(today) for i in items if i.kind == "due" and tomorrow < i.when.date() <= today + timedelta(days=7)]
    return [("Today", todays), ("Tomorrow", next_day), ("Due this week", week)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="show the next 7 days instead of sending alerts")
    parser.add_argument("--done", metavar="TEXT", help="mark upcoming items whose title contains TEXT as done")
    args = parser.parse_args(argv)

    from .config import Config
    from .notify import notify
    from .reminder import load_rows

    Config.load()
    apps, todos, _ = load_rows()
    items, problems = collect(apps, todos)
    now = datetime.now()

    if args.done:
        matched = mark_done(items, args.done, now.date())
        print("\n".join(f"Done: {i.label(now.date())}" for i in matched) or f"Nothing upcoming matches {args.done!r}.")
        return 0
    if args.list:
        for i in items:
            if now - timedelta(hours=1) <= i.when and i.when.date() <= now.date() + timedelta(days=7):
                print(f"{i.when:%a %b %-d %-I:%M %p}  [{i.source or i.kind}] {i.label(now.date())}")
        for p in problems:
            print(p)
        return 0

    sent = _load(SENT_FILE)
    for item in due_for_alert(items, now, sent):
        notify("FRIDAY: coming up", alert_text(item, now))
        sent[item.key] = now.isoformat(timespec="minutes")
    # Forget alerts older than a week so the file stays small.
    cutoff = (now - timedelta(days=7)).isoformat()
    _save(SENT_FILE, {k: v for k, v in sent.items() if v >= cutoff})
    return 0


if __name__ == "__main__":
    sys.exit(main())
