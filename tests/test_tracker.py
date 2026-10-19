import unittest

from tracker.models import Email
from tracker.tracker import apply_email


def email(date, subject="s"):
    return Email(id=date, thread_id=date, sender="x", subject=subject, date=date, text="")


class TrackerTest(unittest.TestCase):
    def test_lifecycle(self):
        rows = []
        self.assertIn("+ Affirm", apply_email(rows, email("2026-10-01"), {"kind": "Applied", "company": "Affirm", "role": "SWE I", "next_action": ""}))
        # Same company, no role named: updates the existing row.
        change = apply_email(rows, email("2026-10-05"), {"kind": "Interview", "company": "Affirm Inc.", "role": "", "next_action": "Pick a slot"})
        self.assertEqual(change, "~ Affirm | SWE I | Applied -> Interview")
        self.assertEqual(rows[0]["Next action"], "Pick a slot")
        # A late confirmation never moves it back.
        self.assertIsNone(apply_email(rows, email("2026-10-06"), {"kind": "Applied", "company": "Affirm", "role": "", "next_action": ""}))
        self.assertEqual(rows[0]["Status"], "Interview")
        # Rejection applies at any stage.
        apply_email(rows, email("2026-10-09"), {"kind": "Rejected", "company": "Affirm", "role": "SWE I", "next_action": ""})
        self.assertEqual((rows[0]["Status"], rows[0]["Last update"]), ("Rejected", "2026-10-09"))
        self.assertEqual(len(rows), 1)

    def test_different_roles_same_company(self):
        rows = []
        apply_email(rows, email("2026-10-01"), {"kind": "Applied", "company": "Amex", "role": "AI Engineer III", "next_action": ""})
        apply_email(rows, email("2026-10-01"), {"kind": "Applied", "company": "Amex", "role": "Data Analyst", "next_action": ""})
        self.assertEqual(len(rows), 2)

    def test_skips_without_company_or_status(self):
        rows = []
        self.assertIsNone(apply_email(rows, email("2026-10-01"), {"kind": "Applied", "company": "", "role": "", "next_action": ""}))
        self.assertIsNone(apply_email(rows, email("2026-10-01"), {"kind": "Other", "company": "Acme", "role": "", "next_action": ""}))
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
