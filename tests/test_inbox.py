"""Texting FRIDAY: reading commands and answering each message once."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime
from unittest import mock

from tracker import inbox
from tracker.inbox import HELP, answer, parse_todo

NOW = datetime(2026, 10, 31, 9, 0)


class ParseTodoTest(unittest.TestCase):
    def test_due_date_at_the_end(self):
        self.assertEqual(parse_todo("call Josh by 2026-11-02", NOW.date()), ("call Josh", "2026-11-02"))

    def test_no_due_date(self):
        self.assertEqual(parse_todo("call Josh", NOW.date()), ("call Josh", ""))

    def test_bad_date_stays_in_the_task(self):
        self.assertEqual(parse_todo("call Josh by 2026-13-40", NOW.date()), ("call Josh by 2026-13-40", ""))


class AnswerTest(unittest.TestCase):
    def test_unknown_and_empty_commands_get_help(self):
        for text in ("rm -rf /", "", "done", "todo   "):
            self.assertEqual(answer(text, NOW), HELP)

    def test_todo_is_added(self):
        table = mock.Mock()
        table.load.return_value = [{"Task": "old"}]
        with mock.patch.object(inbox, "_todo_table", return_value=table):
            self.assertEqual(answer("Todo email Josh by 2026-11-02", NOW), "Added: email Josh (due 2026-11-02)")
        saved = table.save.call_args[0][0]
        self.assertEqual(saved[-1], {"Task": "email Josh", "Due": "2026-11-02", "Source": "texted to FRIDAY"})
        self.assertEqual(len(saved), 2)


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

    def run_main(self, messages):
        sent = []
        with mock.patch.object(inbox, "fetch", return_value=messages) as fetch, \
                mock.patch("tracker.notify.send_ntfy", side_effect=lambda *a: sent.append(a)), \
                mock.patch.object(inbox, "answer", side_effect=lambda text, now: f"re {text}"):
            self.assertEqual(inbox.main([]), 0)
        return fetch.call_args[0], sent

    def test_answers_each_message_on_the_other_topic_and_remembers_the_last(self):
        _, sent = self.run_main([{"id": "m1", "message": "list"}, {"id": "m2", "message": "help"}])
        self.assertEqual(sent, [("out-abc", "FRIDAY: list", "re list"), ("out-abc", "FRIDAY: help", "re help")])
        (topic, since), _ = self.run_main([])
        self.assertEqual((topic, since), ("in-abc", "m2"))
        with open(inbox.STATE_FILE) as f:
            self.assertEqual(json.load(f), {"last_id": "m2"})

    def test_first_run_starts_from_now(self):
        (_, since), sent = self.run_main([])
        self.assertTrue(since.isdigit())
        self.assertEqual(sent, [])

    def test_same_topic_for_both_is_refused(self):
        with mock.patch.dict(os.environ, {"NTFY_INBOX_TOPIC": "out-abc"}):
            self.assertEqual(inbox.main([]), 1)


if __name__ == "__main__":
    unittest.main()
