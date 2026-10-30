"""Deadlines and next steps read from job emails with rules alone."""
import unittest
from datetime import date

from tracker.job_emails import ASSESSMENT, INTERVIEW, OFFER, deadline, extract, next_action
from tracker.models import Email


def email(subject, body, sent="2026-10-23"):
    return Email(id="x", thread_id="x", sender="Recruiting <jobs@acme.com>", subject=subject, date=sent, text=body)


class DeadlineTest(unittest.TestCase):
    def test_deadlines(self):
        cases = [
            ("Please complete the assessment within 5 days.", date(2026, 10, 28)),
            ("Complete it within five business days.", date(2026, 10, 30)),  # Fri 23 Oct + 5 weekdays
            ("This link expires in 72 hours.", date(2026, 10, 26)),
            ("Please finish by November 3.", date(2026, 11, 3)),
            ("The deadline is Friday, Oct 30th, 2026.", date(2026, 10, 30)),
            ("It expires on 11/02/2026.", date(2026, 11, 2)),
            ("Thanks for applying.", None),
            ("We hired in 2019 by May 4.", None),  # long past, not a deadline
        ]
        for text, want in cases:
            with self.subTest(text=text):
                self.assertEqual(deadline(text, "2026-10-23"), want)

    def test_next_actions(self):
        rokt = email("Next steps with Rokt: Skills Assessment", "Please complete the assessment within 7 days.")
        self.assertEqual(next_action(rokt, ASSESSMENT), "Complete the assessment by Fri 30 Oct")
        modivcare = email("Interview - SDET I - Modivcare",
                          "Please share a few dates and times when you're available next week.", sent="2026-10-22")
        self.assertEqual(next_action(modivcare, INTERVIEW), "Reply with your availability")
        offer = email("Your offer", "Please respond by Nov 6.")
        self.assertEqual(next_action(offer, OFFER), "Respond to the offer by Fri 6 Nov")
        self.assertEqual(next_action(email("Thanks", "Thanks for applying."), "Applied"), "")


class SubjectRoleTest(unittest.TestCase):
    def test_role_between_dashes(self):
        found = extract(Email(id="x", thread_id="x", sender="Modivcare Talent Acquisition <modivcare@myworkday.com>",
                              subject="Interview - SDET I - Modivcare", date="2026-10-22",
                              text="We're excited to invite you to the next stage."))
        self.assertEqual((found.company, found.role), ("Modivcare", "SDET I"))


if __name__ == "__main__":
    unittest.main()
