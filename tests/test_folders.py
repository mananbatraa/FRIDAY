import unittest

from tracker.folders import ACTIONS_FOLDER, JOBS_FOLDER, by_folder


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


if __name__ == "__main__":
    unittest.main()
