import unittest
from datetime import date

from tracker import outreach
from tracker.outreach import BOUNCED, FOLLOW_UP_DUE, FOLLOWED_UP, NO_REPLY, REPLIED, WAITING, person, thread_status


def msg(id, day, sender="Manan <me@gmail.com>", sent=False, auto=False, to="Jane Doe <jane.doe@stripe.com>",
        thread="t1", subject="Seeking guidance"):
    return {"id": id, "thread_id": thread, "date": day, "from": sender, "to": to, "subject": subject,
            "auto": auto, "labels": ("SENT",) if sent else ("INBOX",)}


ROW = {"Sent on": "2026-10-01", "Message ID": "m1", "Thread ID": "t1"}
SENT = msg("m1", "2026-10-01", sent=True)


class ThreadStatusTest(unittest.TestCase):
    def status(self, messages, today="2026-10-05"):
        return thread_status(ROW, messages, date.fromisoformat(today), 7)

    def test_waiting_then_due(self):
        self.assertEqual(self.status([SENT]), {"Status": WAITING, "Last reply": "", "Follow up on": "2026-10-08"})
        self.assertEqual(self.status([SENT], today="2026-10-08")["Status"], FOLLOW_UP_DUE)

    def test_reply(self):
        reply = msg("m2", "2026-10-03", sender="Jane Doe <jane.doe@stripe.com>")
        self.assertEqual(self.status([SENT, reply]), {"Status": REPLIED, "Last reply": "2026-10-03", "Follow up on": ""})

    def test_out_of_office_is_not_a_reply(self):
        ooo = msg("m2", "2026-10-02", sender="jane.doe@stripe.com", auto=True)
        self.assertEqual(self.status([SENT, ooo], today="2026-10-09")["Status"], FOLLOW_UP_DUE)

    def test_bounce(self):
        bounce = msg("m2", "2026-10-01", sender="Mail Delivery Subsystem <mailer-daemon@googlemail.com>", auto=True)
        self.assertEqual(self.status([SENT, bounce])["Status"], BOUNCED)

    def test_follow_up_then_no_reply(self):
        nudge = msg("m2", "2026-10-09", sent=True)
        self.assertEqual(self.status([SENT, nudge], today="2026-10-10")["Status"], FOLLOWED_UP)
        self.assertEqual(self.status([SENT, nudge], today="2026-10-16")["Status"], NO_REPLY)

    def test_earlier_messages_in_thread_are_ignored(self):
        earlier = msg("m0", "2026-09-20", sender="jane.doe@stripe.com")
        self.assertEqual(self.status([earlier, SENT])["Status"], WAITING)


class PersonTest(unittest.TestCase):
    def test_parses_name_and_company(self):
        self.assertEqual(person("Jane Doe <Jane.Doe@careers.stripe.com>"), ("Jane Doe", "jane.doe@careers.stripe.com", "Stripe"))
        self.assertEqual(person("raj.kumar@ibm.com"), ("Raj Kumar", "raj.kumar@ibm.com", "IBM"))
        self.assertEqual(person("priya@tcs.co.in"), ("", "priya@tcs.co.in", "TCS"))
        self.assertEqual(person("Sam <sam123@gmail.com>"), ("Sam", "sam123@gmail.com", ""))


class FakeGmail:
    def __init__(self, threads, sent):
        self.threads, self.sent = threads, sent

    def search_messages(self, query, limit=500):
        if query.startswith("from:"):
            return []
        return self.sent

    def thread(self, thread_id):
        return self.threads[thread_id]


class UpdateTest(unittest.TestCase):
    def test_logs_new_sends_and_reports_replies(self):
        nudge = msg("m3", "2026-10-09", sent=True)  # follow-up in the same thread: not a new row
        other = msg("m2", "2026-10-02", sent=True, to="alex@figma.com", thread="t2")
        gmail = FakeGmail({"t1": [SENT, nudge], "t2": [other]},
                          [{"id": "m3", "threadId": "t1"}, {"id": "m2", "threadId": "t2"}, {"id": "m1", "threadId": "t1"}])
        rows = []
        sent, news = outreach.update(gmail, rows, "in:sent", date(2026, 10, 10))
        self.assertEqual([r["Email"] for r in rows], ["jane.doe@stripe.com", "alex@figma.com"])
        self.assertEqual(len(sent), 2)
        self.assertEqual(news, [])  # a first run's overdue emails aren't news
        self.assertEqual([r["Status"] for r in rows], [FOLLOWED_UP, FOLLOW_UP_DUE])

        gmail.threads["t2"].append(msg("m4", "2026-10-11", sender="Alex <alex@figma.com>"))
        sent, news = outreach.update(gmail, rows, "in:sent", date(2026, 10, 11))
        self.assertEqual(sent, [])
        self.assertEqual(news, ["~ Outreach | alex@figma.com (Figma) | Follow-up due -> Replied"])
        self.assertEqual(rows[1]["Last reply"], "2026-10-11")


if __name__ == "__main__":
    unittest.main()
