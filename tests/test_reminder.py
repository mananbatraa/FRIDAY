import json
import os
import unittest
from datetime import datetime
from unittest import mock

from tracker import reminder
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


class MorningTest(unittest.TestCase):
    def test_greeting_quote_list_signoff(self):
        with mock.patch.dict(os.environ, {"FRIDAY_NAME": "Naman"}):
            text = pending([{"Company": "Rokt", "Status": "Assessment", "Next action": "Complete the assessment"}], [],
                           [], NOW, [("Tomorrow", ["CSE 540: Draft (due tomorrow)"]), ("Stock app", ["Momentum: SELL X"])],
                           morning=True)
        lines = text.split("\n")
        self.assertTrue(lines[0].startswith("Good morning, Naman ☀️"))
        self.assertTrue(lines[2].startswith("“") and " — " in lines[2])  # the quote
        self.assertIn("🟠 Tomorrow\n• CSE 540: Draft (due tomorrow)", text)
        self.assertIn("📌 To do\n• Complete the assessment at Rokt", text)
        self.assertIn("📈 Stocks\n• Momentum: SELL X", text)
        self.assertEqual(lines[-1], "I'll keep you posted on everything else. Just lock in. 💪")

    def test_quiet_morning_still_says_hello(self):
        text = pending([], [], [], NOW, [], morning=True)
        self.assertIn("Nothing on the list today", text)


class SendTest(unittest.TestCase):
    def run_main(self, env):
        rows = ([{"Company": "Affirm", "Status": "Interview", "Next action": "Pick a slot", "Rounds": ""}], [], [])
        with mock.patch.dict(os.environ, {"NTFY_TOPIC": "", **env}, clear=False), \
                mock.patch("tracker.daily.extra_sections", return_value=[]), \
                mock.patch.object(reminder, "load_rows", return_value=rows), \
                mock.patch.object(reminder, "send_whatsapp") as whatsapp, \
                mock.patch.object(reminder, "send_telegram") as telegram, \
                mock.patch.object(reminder, "send_imessage") as imessage, \
                mock.patch("builtins.print"):
            code = reminder.main([])
        self.whatsapp = whatsapp
        return code, telegram, imessage

    def test_whatsapp_first(self):
        code, telegram, imessage = self.run_main(
            {"WHATSAPP_PHONE": "+1602", "CALLMEBOT_APIKEY": "k", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "42"})
        self.assertEqual(code, 0)
        self.assertEqual(self.whatsapp.call_args.args[:2], ("+1602", "k"))
        telegram.assert_not_called()
        imessage.assert_not_called()

    def test_telegram_wins_over_imessage(self):
        code, telegram, imessage = self.run_main(
            {"WHATSAPP_PHONE": "", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "42", "REMINDER_PHONE": "+1555"})
        self.assertEqual(code, 0)
        self.assertEqual(telegram.call_args.args[:2], ("t", "42"))
        self.assertIn("Pick a slot at Affirm", telegram.call_args.args[2])
        imessage.assert_not_called()

    def test_imessage_without_telegram(self):
        code, telegram, imessage = self.run_main({"WHATSAPP_PHONE": "", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "", "REMINDER_PHONE": "+1555"})
        self.assertEqual(code, 0)
        telegram.assert_not_called()
        self.assertEqual(imessage.call_args.args[0], "+1555")

    def test_ntfy_before_imessage(self):
        rows = ([{"Company": "Affirm", "Status": "Interview", "Next action": "Pick a slot", "Rounds": ""}], [], [])
        with mock.patch.dict(os.environ, {"WHATSAPP_PHONE": "", "TELEGRAM_BOT_TOKEN": "", "NTFY_TOPIC": "topic",
                                          "REMINDER_PHONE": "+1555"}, clear=False), \
                mock.patch("tracker.daily.extra_sections", return_value=[("Stock app", ["Momentum: SELL X"])]), \
                mock.patch.object(reminder, "load_rows", return_value=rows), \
                mock.patch("tracker.notify.send_ntfy") as ntfy, \
                mock.patch.object(reminder, "send_imessage") as imessage, \
                mock.patch("builtins.print"):
            self.assertEqual(reminder.main([]), 0)
        self.assertEqual(ntfy.call_args.args[0], "topic")
        self.assertIn("Momentum: SELL X", ntfy.call_args.args[2])
        imessage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
