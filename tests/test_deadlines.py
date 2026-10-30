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


if __name__ == "__main__":
    unittest.main()
