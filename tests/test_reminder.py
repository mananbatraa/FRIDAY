import json
import unittest
from datetime import datetime

from tracker.reminder import pending

NOW = datetime(2026, 10, 30, 8, 0)  # a Friday


def app(company, status="Interview", action="", rounds=()):
    return {"Company": company, "Status": status, "Next action": action, "Rounds": json.dumps(list(rounds))}


class PendingTest(unittest.TestCase):
    def test_nothing_pending(self):
        self.assertEqual(pending([app("Affirm")], [], [], NOW), "")

    def test_rounds_in_the_next_48_hours(self):
        apps = [app("Stripe", rounds=[{"When": "2026-10-30T14:00", "Round": "Onsite"},
                                      {"When": "2026-11-05T10:00", "Round": "Final"}]),
                app("Ramp", rounds=[{"When": "2026-10-31T09:30"}, {"When": "not a date"}])]
        text = pending(apps, [], [], NOW)
        self.assertIn("Interviews in the next 48 hours (2)", text)
        self.assertIn("• Onsite at Stripe, today 2:00 PM", text)
        self.assertIn("• Interview at Ramp, tomorrow 9:30 AM", text)
        self.assertNotIn("Final", text)

    def test_todos_and_next_actions(self):
        todos = [{"Task": "Send portfolio", "Company": "Figma", "Due": "2026-10-29", "Done": ""},
                 {"Task": "Thank-you note", "Company": "", "Due": "2026-10-31", "Done": ""},
                 {"Task": "Done already", "Company": "", "Due": "", "Done": "2026-10-28"}]
        apps = [app("Affirm", action="Pick a slot"), app("Old Co", status="Rejected", action="Reply")]
        lines = pending(apps, todos, [], NOW).splitlines()
        self.assertEqual(lines[1:], ["To-dos (3)",
                                     "• Send portfolio at Figma (overdue, was due Oct 29)",
                                     "• Thank-you note (due tomorrow)",
                                     "• Pick a slot at Affirm"])

    def test_outreach_follow_ups(self):
        rows = [{"Name": "Jane Doe", "Email": "jane@stripe.com", "Company": "Stripe", "Status": "Follow-up due"},
                {"Name": "", "Email": "bob@ramp.com", "Company": "", "Status": "Follow-up due"},
                {"Name": "Al", "Email": "al@x.com", "Company": "X", "Status": "Waiting"}]
        text = pending([], [], rows, NOW)
        self.assertIn("Outreach follow-ups due (2)\n• Jane Doe (Stripe)\n• bob@ramp.com", text)

    def test_long_lists_are_cut(self):
        todos = [{"Task": f"Task {i}", "Company": "", "Due": "", "Done": ""} for i in range(11)]
        text = pending([], todos, [], NOW)
        self.assertIn("(and 3 more)", text)
        self.assertNotIn("Task 8", text)


if __name__ == "__main__":
    unittest.main()
