"""Phone alerts from the email check: only what needs you."""
import unittest

from tracker.main import phone_alert


class PhoneAlertTest(unittest.TestCase):
    def test_only_confirmations_stay_quiet(self):
        changes = [f"+ Company {i} | Role | Applied" for i in 115 * [0]]
        self.assertIsNone(phone_alert(changes))
        self.assertIsNone(phone_alert(["~ Citi | AI Engineer | Applied -> Rejected"]))

    def test_interview_alerts_with_counts(self):
        changes = ["+ Amex | Analyst | Applied", "+ Cadence | SWE | Applied",
                   "~ Modivcare | SDET I | Applied -> Interview", "~ Citi | AI Engineer | Applied -> Rejected",
                   "~ Outreach | Samina Tushi (Kodiak) | Waiting -> Replied"]
        title, message = phone_alert(changes)
        self.assertEqual(title, "FRIDAY: 2 need you")
        self.assertEqual(message, "Modivcare | SDET I | Applied -> Interview; Outreach | Samina Tushi (Kodiak) | "
                                  "Waiting -> Replied. Also 2 new applications, 1 rejection.")


if __name__ == "__main__":
    unittest.main()
