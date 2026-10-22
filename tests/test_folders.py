import unittest
from datetime import date

from tracker.folders import ACTIONS_FOLDER, JOBS_FOLDER, by_folder, recent_codes


class FoldersTest(unittest.TestCase):
    def test_groups_by_kind(self):
        logged = [
            {"Kind": "Applied", "Message ID": "a"},
            {"Kind": "Rejected", "Message ID": "b"},
            {"Kind": "Assessment", "Message ID": "c"},
            {"Kind": "Interview", "Message ID": "d"},
            {"Kind": "Verification", "Message ID": "e"},
            {"Kind": "Other", "Message ID": "f"},
        ]
        self.assertEqual(by_folder(logged), {JOBS_FOLDER: ["a", "b"], ACTIONS_FOLDER: ["c", "d"]})

    def test_actions_folder_is_inside_usa_jobs(self):
        self.assertEqual(ACTIONS_FOLDER, "USA Jobs/Actions to be Taken")

    def test_recent_codes(self):
        logged = [
            {"Kind": "Verification", "Message ID": "old", "Date": "2026-09-01"},
            {"Kind": "Verification", "Message ID": "week", "Date": "2026-10-16"},
            {"Kind": "Verification", "Message ID": "today", "Date": "2026-10-22"},
            {"Kind": "Applied", "Message ID": "job", "Date": "2026-10-22"},
        ]
        self.assertEqual(recent_codes(logged, date(2026, 10, 22)), ["week", "today"])
        self.assertEqual(recent_codes(logged, date(2026, 10, 22), everything=True), ["old", "week", "today"])


if __name__ == "__main__":
    unittest.main()
