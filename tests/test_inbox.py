"""Texting FRIDAY: reading what was typed, the commands, and answering each message once."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime
from unittest import mock

from tracker import deadlines, inbox
from tracker.deadlines import Item
from tracker.inbox import HELP, answer, parse, parse_day, parse_todo

NOW = datetime(2026, 10, 31, 9, 0)  # a Saturday
TODAY = NOW.date()


class ParseTest(unittest.TestCase):
    def test_phone_typing(self):
        self.assertEqual(parse("List."), ("list", ""))
        self.assertEqual(parse("  Done HW3!  "), ("done", "HW3"))
        self.assertEqual(parse("What's due today?"), ("list", ""))
        self.assertEqual(parse("whats due"), ("list", ""))
        self.assertEqual(parse("help?"), ("help", ""))
        self.assertEqual(parse(""), ("help", ""))
        self.assertEqual(parse("hi"), ("unknown", "hi"))
        self.assertEqual(parse("👍"), ("unknown", "👍"))


class ParseDayTest(unittest.TestCase):
    def test_words_and_dates(self):
        self.assertEqual(parse_day("today", TODAY), date(2026, 10, 31))
        self.assertEqual(parse_day("Tomorrow", TODAY), date(2026, 11, 1))
        self.assertEqual(parse_day("fri", TODAY), date(2026, 11, 6))
        self.assertEqual(parse_day("saturday", TODAY), TODAY)
        self.assertEqual(parse_day("Nov 2", TODAY), date(2026, 11, 2))
        self.assertEqual(parse_day("2nd november", TODAY), date(2026, 11, 2))
        self.assertEqual(parse_day("11/2", TODAY), date(2026, 11, 2))
        self.assertEqual(parse_day("jan 5", TODAY), date(2027, 1, 5))  # already past this year
        self.assertEqual(parse_day("2026-11-02", TODAY), date(2026, 11, 2))
        for nothing in ("eggs", "2 eggs", "13/40", "feb 30", "friday night"):
            self.assertIsNone(parse_day(nothing, TODAY), nothing)


class ParseTodoTest(unittest.TestCase):
    def test_due_dates(self):
        self.assertEqual(parse_todo("call Josh by 2026-11-02", TODAY), ("call Josh", "2026-11-02"))
        self.assertEqual(parse_todo("call Josh tomorrow", TODAY), ("call Josh", "2026-11-01"))
        self.assertEqual(parse_todo("email Josh by Nov 2", TODAY), ("email Josh", "2026-11-02"))
        self.assertEqual(parse_todo("email Josh on fri", TODAY), ("email Josh", "2026-11-06"))

    def test_no_due_date(self):
        self.assertEqual(parse_todo("call Josh", TODAY), ("call Josh", ""))
        self.assertEqual(parse_todo("buy 2 eggs", TODAY), ("buy 2 eggs", ""))
        self.assertEqual(parse_todo("tomorrow", TODAY), ("tomorrow", ""))
        self.assertEqual(parse_todo("call Josh by 2026-13-40", TODAY), ("call Josh by 2026-13-40", ""))


class AnswerTest(unittest.TestCase):
    def test_unknown_says_so(self):
        self.assertEqual(answer("rm -rf /", NOW), f"I didn't get 'rm -rf /'.\n\n{HELP}")
        self.assertEqual(answer("help", NOW), HELP)

    def test_missing_text(self):
        self.assertEqual(answer("done", NOW), "Done what? Send part of its name, like: done hw3")
        self.assertEqual(answer("todo   ", NOW), "Add what? Like: todo email Josh by fri")

    def test_todo_is_added(self):
        table = mock.Mock()
        table.load.return_value = [{"Task": "old"}]
        with mock.patch.object(inbox, "_todo_table", return_value=table):
            self.assertEqual(answer("Todo email Josh by nov 2", NOW), "Added: email Josh (due Mon Nov 2)")
        saved = table.save.call_args[0][0]
        self.assertEqual(saved[-1], {"Task": "email Josh", "Due": "2026-11-02", "Source": "texted to FRIDAY"})
        self.assertEqual(len(saved), 2)

    def test_submit_reminds_on_the_mac_only(self):
        with mock.patch("tracker.notify.notify") as notify:
            self.assertIn("tell Claude", answer("submit", NOW))
        self.assertFalse(notify.call_args.kwargs["phone"])


REPORTS = [Item(datetime(2026, 10, 31 + d, 11, 30) if d < 1 else datetime(2026, 11, d, 11, 30),
                "Hackathon progress report (AM): say submit", "due") for d in range(0, 4)]
QUIZ = Item(datetime(2026, 11, 1, 23, 59), "CSE 540: Graded Quiz: Module 2", "due", True)
CSE579 = Item(datetime(2026, 11, 1, 23, 59), "CSE 579: Module 4-quiz", "due", True)


class DoneTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(deadlines, "DONE_FILE", os.path.join(self.dir.name, "done.json"))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.dir.cleanup()

    def say(self, text):
        def collect(apps, todos, include_done=False):
            done = deadlines.load_done()
            return [i for i in REPORTS + [QUIZ, CSE579] if include_done or i.key not in done], []
        with mock.patch("tracker.reminder.load_rows", return_value=([], [], [])), \
                mock.patch("tracker.deadlines.collect", side_effect=collect):
            return answer(text, NOW)

    def test_a_repeating_item_marks_only_the_next_one(self):
        reply = self.say("done report")
        self.assertEqual(reply, "Done: Hackathon progress report (AM): say submit (due today 11:30 AM)\n"
                                "(The other 3 like it are untouched.)")
        self.assertEqual(list(deadlines.load_done()), [REPORTS[0].key])
        self.say("done report")
        self.assertEqual(list(deadlines.load_done()), [REPORTS[0].key, REPORTS[1].key])

    def test_words_in_any_order(self):
        self.assertTrue(self.say("done cse 540 quiz").startswith("Done: CSE 540: Graded Quiz"))

    def test_several_different_items_asks_which(self):
        reply = self.say("done quiz")
        self.assertTrue(reply.startswith("Which one?"), reply)
        self.assertIn("Or: done all quiz", reply)
        self.assertEqual(deadlines.load_done(), {})
        self.say("done all quiz")
        self.assertEqual(set(deadlines.load_done()), {QUIZ.key, CSE579.key})

    def test_undo(self):
        self.say("done hw3")  # nothing matches: no harm
        self.say("done cse 540 quiz")
        self.assertEqual(self.say("undo 540"), "Not done: CSE 540: Graded Quiz: Module 2 (due tomorrow)")
        self.assertEqual(deadlines.load_done(), {})
        self.assertTrue(self.say("undo 540").startswith("Nothing marked done matches"))


class MainTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.dir.name)
        self.env = mock.patch.dict(os.environ, {"NTFY_INBOX_TOPIC": "in-abc", "NTFY_TOPIC": "out-abc"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.cwd)
        self.dir.cleanup()

    def run_main(self, messages, reply=lambda text, now: f"re {text}"):
        sent = []
        with mock.patch.object(inbox, "fetch", return_value=messages) as fetch, \
                mock.patch("tracker.notify.send_ntfy", side_effect=lambda *a, **k: sent.append(a)), \
                mock.patch.object(inbox, "answer", side_effect=reply):
            self.assertEqual(inbox.main([]), 0)
        return fetch.call_args[0], sent

    def test_answers_each_message_on_the_other_topic_and_remembers_the_last(self):
        _, sent = self.run_main([{"id": "m1", "message": "list"}, {"id": "m2", "message": "help"}])
        self.assertEqual(sent, [("out-abc", "FRIDAY: list", "re list"), ("out-abc", "FRIDAY: help", "re help")])
        (topic, since), _ = self.run_main([])
        self.assertEqual((topic, since), ("in-abc", "m2"))
        with open(inbox.STATE_FILE) as f:
            self.assertEqual(json.load(f), {"last_id": "m2"})

    def test_slow_commands_say_on_it_first(self):
        _, sent = self.run_main([{"id": "m1", "message": "Pending"}])
        self.assertEqual([s[2] for s in sent], ["On it, give me a few seconds…", "re Pending"])

    def test_an_error_is_answered_and_skipped(self):
        def broken(text, now):
            raise KeyError("Due")
        _, sent = self.run_main([{"id": "m1", "message": "list"}], reply=broken)
        self.assertEqual(sent[0][2], "Something went wrong: KeyError: 'Due'")
        with open(inbox.STATE_FILE) as f:
            self.assertEqual(json.load(f), {"last_id": "m1"})

    def test_long_replies_are_cut_to_fit(self):
        _, sent = self.run_main([{"id": "m1", "message": "list"}], reply=lambda t, n: "• item\n" * 1000)
        self.assertLessEqual(len(sent[0][2].encode()), inbox.MAX_REPLY + 4)
        self.assertTrue(sent[0][2].endswith("\n…"))

    def test_first_run_starts_from_now(self):
        (_, since), sent = self.run_main([])
        self.assertTrue(since.isdigit())
        self.assertEqual(sent, [])

    def test_same_topic_for_both_is_refused(self):
        with mock.patch.dict(os.environ, {"NTFY_INBOX_TOPIC": "out-abc"}):
            self.assertEqual(inbox.main([]), 1)


if __name__ == "__main__":
    unittest.main()
