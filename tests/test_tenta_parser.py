from __future__ import annotations

import unittest
from pathlib import Path

from tracker.models import Email, normalize_company
from tracker.tenta_parser import parse

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load_sample(name: str) -> Email:
    raw = (SAMPLES / name).read_text(encoding="utf-8")
    head, _, body = raw.partition("\n\n")
    headers = dict(line.split(": ", 1) for line in head.splitlines())
    return Email(id=name, thread_id=name, sender=headers["From"], subject=headers["Subject"],
                 date=headers["Date"], text=body)


class TentaParserTest(unittest.TestCase):
    def test_sentence_style(self):
        apps = parse(load_sample("placeholder_single.txt"))
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].company, "Acme Corp")
        self.assertEqual(apps[0].job_title, "Data Analyst")
        self.assertEqual(apps[0].job_link, "https://boards.greenhouse.io/acme/jobs/123456")
        self.assertEqual(apps[0].applied_on, "2026-10-18")

    def test_labelled_fields(self):
        apps = parse(load_sample("placeholder_fields.txt"))
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].company, "Globex Pvt Ltd")
        self.assertEqual(apps[0].job_title, "Backend Engineer")
        self.assertEqual(apps[0].location, "Bengaluru (Hybrid)")
        self.assertEqual(apps[0].job_link, "https://jobs.lever.co/globex/abc-123")

    def test_batch_email(self):
        apps = parse(load_sample("placeholder_batch.txt"))
        self.assertEqual([a.company for a in apps], ["Initech", "Umbrella Corporation"])
        self.assertEqual([a.job_title for a in apps], ["Software Engineer I", "ML Engineer"])
        self.assertEqual(apps[1].job_link, "https://jobs.ashbyhq.com/umbrella/77")

    def test_subject_fallback(self):
        email = Email(id="x", thread_id="x", sender="", date="2026-10-19",
                      subject="Your application to Hooli for Product Analyst", text="Thanks!")
        apps = parse(email)
        self.assertEqual((apps[0].company, apps[0].job_title), ("Hooli", "Product Analyst"))

    def test_unrelated_email(self):
        email = Email(id="y", thread_id="y", sender="", date="2026-10-19",
                      subject="Your weekly newsletter", text="Nothing about jobs here.")
        self.assertEqual(parse(email), [])

    def test_company_dedupe_key(self):
        self.assertEqual(normalize_company("Globex Pvt. Ltd."), "globex")
        self.assertEqual(normalize_company("Acme, Inc."), "acme")


if __name__ == "__main__":
    unittest.main()
