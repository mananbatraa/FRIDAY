"""The extra reminder sections: Canvas, emails waiting on a reply, and the stock app."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from tracker.daily import canvas_tasks, needs_reply, stock_actions

NOW = datetime(2026, 10, 30, 9, 0)

ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261102
DTEND;VALUE=DATE:20261102
SUMMARY:Homework 4 [CSE 551]
END:VEVENT
BEGIN:VEVENT
DTSTART:20261031T065900Z
DTEND:20261031T065900Z
SUMMARY:Quiz 3: Merkle trees and EC
 DSA [CSE 539]
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261120
SUMMARY:Final project [CSE 551]
END:VEVENT
BEGIN:VEVENT
DTSTART:20261030T220000Z
DTEND:20261030T230000Z
SUMMARY:CSE 540 - TA Office Hours [2026FallB-T-CSE540-82242]
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE;VALUE=DATE:20261101
SUMMARY:Submission: Draft Smart Contract Design [2026FallB-T-CSE540-82242]
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261020
SUMMARY:Old homework [CSE 551]
END:VEVENT
END:VCALENDAR
"""


class CanvasTest(unittest.TestCase):
    def test_this_weeks_items_soonest_first(self):
        lines = canvas_tasks(ICS, NOW)
        # Old work, work weeks away and office hours are left out.
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("Quiz 3: Merkle trees and ECDSA [CSE 539] (due"))  # folded line joined
        self.assertEqual(lines[1], "CSE 540: Submission: Draft Smart Contract Design (due Sun Nov 1)")
        self.assertEqual(lines[2], "Homework 4 [CSE 551] (due Mon Nov 2)")


def msg(sender, auto=False):
    return {"from": sender, "subject": "Re: coffee chat", "date": "2026-10-28", "auto": auto}


class NeedsReplyTest(unittest.TestCase):
    def test_person_wrote_last(self):
        self.assertEqual(needs_reply([msg("Me <me@x.com>"), msg("Priya <priya@acme.com>")], "me@x.com")["from"],
                         "Priya <priya@acme.com>")

    def test_no_reply_needed(self):
        self.assertIsNone(needs_reply([msg("Priya <priya@acme.com>"), msg("Me <me@x.com>")], "me@x.com"))
        self.assertIsNone(needs_reply([msg("Acme <no-reply@acme.com>")], "me@x.com"))
        self.assertIsNone(needs_reply([msg("Priya <priya@acme.com>", auto=True)], "me@x.com"))  # out of office
        self.assertIsNone(needs_reply([], "me@x.com"))
        self.assertIsNone(needs_reply([{**msg("et-hackathons <events@et.com>"), "bulk": True}], "me@x.com"))
        self.assertIsNone(needs_reply([{**msg("HR <hr@acme.com>"), "subject": "Verify your candidate account"}],
                                      "me@x.com"))


class StockTest(unittest.TestCase):
    def test_todays_actions_only(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "paper").mkdir()
            (Path(folder) / "paper" / "momentum.json").write_text(json.dumps({
                "log": [["2026-10-30 08:30", "SELL Illumina (ILMN) at about $233.80: down 14%."],
                        ["2026-10-30 11:06", "SELL Later Co, after the report"],
                        ["2026-10-30 07:13", "FYI Sandisk (SNDK) is -9% today. No action."],
                        ["2026-10-29 10:00", "BUY Old Co yesterday"]],
                "pending": [{"side": "buy", "ticker": "DIXON.NS", "info": {"name": "Dixon"}}]}))
            (Path(folder) / "paper" / "account_momentum.json").write_text("{}")
            self.assertEqual(stock_actions(folder, NOW), [
                "Momentum: SELL Illumina (ILMN) at about $233.80: down 14%.",
                "Momentum: BUY Dixon at the next open"])

    def test_not_set_up(self):
        self.assertEqual(stock_actions("", NOW), [])


if __name__ == "__main__":
    unittest.main()
