"""The extra reminder sections: Canvas, emails waiting on a reply, and the stock app."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from tracker.daily import canvas_tasks, needs_reply, stock_summary

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
    def write(self, folder, name, state, account=None):
        (Path(folder) / "paper").mkdir(exist_ok=True)
        (Path(folder) / "paper" / f"{name}.json").write_text(json.dumps({"capital": 3500000, **state}))
        if account is not None:
            (Path(folder) / "paper" / f"account_{name}.json").write_text(json.dumps(account))

    def test_summary_with_trades(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "momentum", {
                "history": [["2026-10-30 08:58", 3587500, 0.013, -0.012], ["2026-10-30 13:28", 1, 0, 0]],
                "log": [["2026-10-30 08:30", "SELL Illumina, Inc. (ILMN) at about $233.80: down 14%."],
                        ["2026-10-30 07:13", "FYI Sandisk (SNDK) is -9% today. No action."],
                        ["2026-10-30 11:06", "SELL Later Co, after the report"],
                        ["2026-10-28 10:00", "BUY Old Co, more than a day ago"]],
                "pending": [{"side": "buy", "ticker": "DIXON.NS", "info": {"name": "Dixon"}}]},
                account={"notes": ["2026-10-30 08:31 SELL 3 × Illumina at ₹19,400.00 (stop-loss)",
                                   "2026-10-27 09:15 BUY 2 × Old at ₹1.00 (bought)"]})
            self.assertEqual(stock_summary(folder, NOW), [
                "Momentum ₹35.88 L (+2.5%) · Nifty 50 +1.3% · S&P 500 −1.2% since 26 Oct",
                "Last 24h: Momentum: SELL Illumina, Inc. (ILMN)",
                "₹1L Momentum: SELL 3 × Illumina at ₹19,400.00 (stop-loss)",
                "Update your GTT stop orders for the ₹1L accounts (see the stock dashboard)",
                "At the next open: Momentum: BUY Dixon"])

    def test_quiet_day(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "multifactor", {"history": [["2026-10-30 08:00", 3465000, 0.01, -0.01]], "log": []})
            self.assertEqual(stock_summary(folder, NOW)[-1], "No trades. The rules say hold.")

    def test_not_set_up(self):
        self.assertEqual(stock_summary("", NOW), [])


if __name__ == "__main__":
    unittest.main()
