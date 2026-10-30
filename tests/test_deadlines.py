"""Dated items from every source, the 30-minute alerts, and marking things done."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime
from unittest import mock

from tracker import deadlines
from tracker.deadlines import Item, alert_text, calendar_items, canvas_items, due_for_alert, report_sections, table_items

NOW = datetime(2026, 11, 1, 23, 35)

CANVAS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE;VALUE=DATE:20261101
SUMMARY:Submission: Draft Smart Contract Design [2026FallB-T-CSE540-82242]
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE-TIME:20261105T190000Z
SUMMARY:CSE 540: Engr Blockchain Applications (2026 Fall B) Instructor led live session [2026FallB-T-CSE540-82242]
END:VEVENT
BEGIN:VEVENT
DTSTART:20261105T220000Z
SUMMARY:CSE 540: Engr Blockchain Applications (2026 Fall B) - TA Office Hours [2026FallB-T-CSE540-82242]
END:VEVENT
END:VCALENDAR
"""

CALENDAR = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20261102T100000
SUMMARY:Call with Samina (Kodiak)
END:VEVENT
BEGIN:VEVENT
DTSTART:20261102T110000
SUMMARY:Cancelled sync
STATUS:CANCELLED
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261102
SUMMARY:Diwali
END:VEVENT
END:VCALENDAR
"""


class SourcesTest(unittest.TestCase):
    def test_canvas(self):
        items = canvas_items(CANVAS)
        self.assertEqual(len(items), 2)  # office hours left out
        work, live = items
        self.assertEqual((work.kind, work.title, work.when), ("due", "CSE 540: Submission: Draft Smart Contract Design",
                                                             datetime(2026, 11, 1, 23, 59)))  # all-day: due 11:59 PM
        self.assertEqual((live.kind, live.title), ("event", "CSE 540: Instructor led live session"))

    def test_calendar(self):
        items = calendar_items(CALENDAR)
        self.assertEqual([i.title for i in items], ["Call with Samina (Kodiak)", "Diwali"])  # cancelled left out
        self.assertTrue(items[1].all_day)

    def test_tables(self):
        apps = [{"Company": "Modivcare", "Status": "Interview",
                 "Rounds": json.dumps([{"When": "2026-11-03T10:00", "Round": "Technical interview"}])}]
        todos = [{"Task": "Send resume to Priya", "Due": "2026-11-02", "Done": ""},
                 {"Task": "Old one", "Due": "2026-11-02", "Done": "2026-11-01"}, {"Task": "No date", "Due": ""}]
        self.assertEqual([i.title for i in table_items(apps, todos)],
                         ["Technical interview with Modivcare", "Send resume to Priya"])


class AlertTest(unittest.TestCase):
    def test_thirty_minutes_before_once(self):
        soon = Item(datetime(2026, 11, 1, 23, 59), "CSE 540: Draft", "due", True)
        later = Item(datetime(2026, 11, 2, 10, 0), "Call with Samina", "event")
        holiday = Item(datetime(2026, 11, 1, 0, 0), "Diwali", "event", all_day=True)
        self.assertEqual(due_for_alert([soon, later, holiday], NOW, {}), [soon])
        self.assertEqual(due_for_alert([soon], NOW, {soon.key: "sent"}), [])  # never twice
        self.assertEqual(alert_text(soon, NOW), "CSE 540: Draft: due in 24 min (11:59 PM)")
        call = Item(datetime(2026, 11, 2, 10, 0), "Call with Samina", "event")
        self.assertEqual(alert_text(call, datetime(2026, 11, 2, 9, 30)), "Call with Samina: starts in 30 min (10:00 AM)")

    def test_report(self):
        morning = datetime(2026, 11, 1, 8, 0)
        items = [Item(datetime(2026, 11, 1, 23, 59), "CSE 540: Draft", "due", True),
                 Item(datetime(2026, 11, 1, 15, 0), "Call with Samina", "event"),
                 Item(datetime(2026, 11, 6, 23, 59), "CSE 598: HW3", "due", True)]
        today, week = report_sections(items, morning)
        self.assertEqual(today, ("Today", ["CSE 540: Draft (due today)", "Call with Samina (today 3:00 PM)"]))
        self.assertEqual(week, ("Due this week", ["CSE 598: HW3 (due Fri Nov 6)"]))


class DoneTest(unittest.TestCase):
    def test_mark_done(self):
        items = [Item(datetime(2026, 11, 1, 23, 59), "CSE 540: Submission: Draft Smart Contract Design", "due", True),
                 Item(datetime(2026, 11, 6, 23, 59), "CSE 598: HW3", "due", True)]
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(deadlines, "DONE_FILE", os.path.join(folder, "done.json")):
            matched = deadlines.mark_done(items, "smart contract", date(2026, 10, 30))
            self.assertEqual([i.title for i in matched], [items[0].title])
            self.assertIn(items[0].key, deadlines.load_done())
            self.assertNotIn(items[1].key, deadlines.load_done())


class CalendarRulesTest(unittest.TestCase):
    def test_time_zone_tag(self):
        ics = ("BEGIN:VEVENT\nDTSTART;TZID=America/Chicago:20261102T103000\nSUMMARY:Recruiter call\nEND:VEVENT\n")
        with mock.patch.dict(os.environ, {"TZ": "America/Phoenix"}):
            import time
            time.tzset()
            try:
                (when, title, _), = deadlines.parse_events(ics, datetime(2026, 11, 1))
            finally:
                os.environ.pop("TZ", None)
                time.tzset()
        self.assertEqual((title, when), ("Recruiter call", datetime(2026, 11, 2, 9, 30)))  # 10:30 Chicago = 9:30 Phoenix

    def test_weekly_repeat(self):
        ics = ("BEGIN:VEVENT\nDTSTART:20261005T100000\nRRULE:FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20261111T235959Z\n"
               "EXDATE:20261104T100000\nSUMMARY:Team sync\nEND:VEVENT\n")
        starts = [w for w, _, _ in deadlines.parse_events(ics, datetime(2026, 11, 1))]
        # From a day before Nov 1: Mon Nov 2, (Wed Nov 4 skipped), Mon Nov 9, Wed Nov 11; then the rule ends.
        self.assertEqual(starts, [datetime(2026, 11, 2, 10), datetime(2026, 11, 9, 10), datetime(2026, 11, 11, 10)])

    def test_finished_repeat(self):
        ics = ("BEGIN:VEVENT\nDTSTART;TZID=America/Chicago:20260622T103000\n"
               "RRULE:FREQ=WEEKLY;UNTIL=20260623T153000Z;BYDAY=MO\nSUMMARY:Genpact daily connect\nEND:VEVENT\n")
        self.assertEqual(deadlines.parse_events(ics, datetime(2026, 11, 1)), [])


if __name__ == "__main__":
    unittest.main()
