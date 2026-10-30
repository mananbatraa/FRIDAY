import os
import tempfile
import unittest
from unittest import mock

from tracker import open_jobs
from tracker.open_jobs import Job, load_opened, log_opened, normalize, parse_jobs, select

ROW = """<tr>
<td>{company}</td>
<td>{role}</td>
<td>{location}</td>
<td>{apply}</td>
<td>{age}</td>
</tr>"""
APPLY = ('<div align="center"><a href="{url}?utm_source=Simplify&ref=Simplify"><img src="x.png" width="52" alt="Apply"></a> '
         '<a href="https://simplify.jobs/p/1?utm_source=GHList"><img src="y.png" width="28" alt="Simplify"></a></div>')


def row(company, role, location, url=None, age="1d"):
    return ROW.format(company=company, role=role, location=location, age=age,
                      apply=APPLY.format(url=url) if url else "🔒")


README = f"""## 💻 Software Engineering New Grad Roles
<table><thead><tr><th>Company</th></tr></thead>
<tbody>
{row('<strong><a href="https://simplify.jobs/c/Acme">Acme</a></strong>', "Software Engineer", "Austin, TX", "https://acme.com/jobs/1", "0d")}
{row("↳", "Backend Engineer", "Remote in USA", "https://acme.com/jobs/2", "3d")}
{row("↳", "Closed Role", "NYC")}
{row('<strong><a href="https://simplify.jobs/c/Big">🔥 Big</a></strong>', "SDE 1 🛂",
     "<details><summary><strong>2 locations</strong></summary>Seattle, WA</br>Tempe, AZ</details>",
     "https://big.com/jobs/9", "2mo")}
{row("<strong>Gov Co</strong>", "Engineer 🇺🇸", "McLean, VA", "https://gov.com/a", "10d")}
</tbody></table>
<details><summary>Inactive roles</summary>
<table><tbody>
{row("<strong>Old</strong>", "Old Role", "SF", "https://old.com/1")}
</tbody></table></details>

## 📱 Product Management New Grad Roles
<table><tbody>
{row("<strong>PM Co</strong>", "PM", "SF", "https://pm.com/1")}
</tbody></table>
"""


class ParseTest(unittest.TestCase):
    def test_active_software_roles_only(self):
        jobs = parse_jobs(README)
        self.assertEqual([j.url.split("?")[0] for j in jobs],
                         ["https://acme.com/jobs/1", "https://acme.com/jobs/2", "https://big.com/jobs/9", "https://gov.com/a"])

    def test_sub_rows_take_the_company_above(self):
        jobs = parse_jobs(README)
        self.assertEqual(jobs[1].company, "Acme")
        self.assertEqual(jobs[1].role, "Backend Engineer")

    def test_multiple_locations(self):
        self.assertEqual(parse_jobs(README)[2].location, "Seattle, WA / Tempe, AZ")

    def test_age_in_days(self):
        self.assertEqual([j.age_days for j in parse_jobs(README)], [0, 3, 60, 10])


class SelectTest(unittest.TestCase):
    def setUp(self):
        self.jobs = parse_jobs(README)

    def test_skips_already_opened_even_with_other_tracking_params(self):
        opened = {normalize("https://acme.com/jobs/1?utm_source=GHList")}
        self.assertNotIn("acme.com/jobs/1", " ".join(j.url for j in select(self.jobs, opened)))

    def test_filters(self):
        self.assertEqual(len(select(self.jobs, max_age=7)), 2)
        self.assertEqual([j.company for j in select(self.jobs, locations=["remote", "AZ"])], ["Acme", "🔥 Big"])
        self.assertEqual(len(select(self.jobs, skip_no_sponsor=True)), 3)
        self.assertEqual(len(select(self.jobs, skip_citizen=True)), 3)

    def test_duplicate_links_open_once(self):
        self.assertEqual(len(select(self.jobs + self.jobs)), 4)


class LogTest(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "opened.csv")
            self.assertEqual(load_opened(path), set())
            log_opened(path, [Job("Acme", "SWE", "Austin, TX", "https://acme.com/jobs/1?ref=Simplify", "0d")])
            log_opened(path, [Job("Big", "SDE", "Seattle, WA", "https://big.com/jobs/9", "1d")])
            self.assertEqual(load_opened(path), {"https://acme.com/jobs/1", "https://big.com/jobs/9"})


class MainTest(unittest.TestCase):
    def test_opens_in_batches_and_logs(self):
        with tempfile.TemporaryDirectory() as d:
            readme, log = os.path.join(d, "README.md"), os.path.join(d, "opened.csv")
            with open(readme, "w", encoding="utf-8") as f:
                f.write(README)
            with mock.patch.object(open_jobs, "open_tab") as tab, mock.patch.object(open_jobs.time, "sleep"), \
                    mock.patch("builtins.input", side_effect=["", "q"]) as ask, mock.patch("builtins.print"):
                open_jobs.main(["--readme", readme, "--log", log, "--batch", "3"])
                self.assertEqual(tab.call_count, 4)
                self.assertEqual(ask.call_count, 1)
            self.assertEqual(len(load_opened(log)), 4)
            with mock.patch.object(open_jobs, "open_tab") as tab, mock.patch("builtins.print"):
                open_jobs.main(["--readme", readme, "--log", log])
                tab.assert_not_called()

    def test_closes_each_window_after_the_wait(self):
        with tempfile.TemporaryDirectory() as d:
            readme, log = os.path.join(d, "README.md"), os.path.join(d, "opened.csv")
            with open(readme, "w", encoding="utf-8") as f:
                f.write(README)
            with mock.patch.object(open_jobs.sys, "platform", "darwin"), \
                    mock.patch.object(open_jobs, "open_window", side_effect=["11", "12"]) as win, \
                    mock.patch.object(open_jobs, "close_window") as close, \
                    mock.patch.object(open_jobs, "countdown", return_value=True) as wait, \
                    mock.patch.object(open_jobs, "open_tab") as tab, mock.patch("builtins.print"):
                open_jobs.main(["--readme", readme, "--log", log, "--batch", "3", "--wait", "120", "--close",
                                "--browser", "Google Chrome"])
            self.assertEqual([len(c.args[0]) for c in win.call_args_list], [3, 1])
            self.assertEqual([c.args for c in close.call_args_list], [("11", "Google Chrome"), ("12", "Google Chrome")])
            self.assertEqual(wait.call_count, 2)
            tab.assert_not_called()

    def test_stopping_leaves_the_tabs_open(self):
        with tempfile.TemporaryDirectory() as d:
            readme, log = os.path.join(d, "README.md"), os.path.join(d, "opened.csv")
            with open(readme, "w", encoding="utf-8") as f:
                f.write(README)
            with mock.patch.object(open_jobs.sys, "platform", "darwin"), \
                    mock.patch.object(open_jobs, "open_window", return_value="11") as win, \
                    mock.patch.object(open_jobs, "close_window") as close, \
                    mock.patch.object(open_jobs, "countdown", return_value=False), mock.patch("builtins.print"):
                open_jobs.main(["--readme", readme, "--log", log, "--batch", "3", "--wait", "120", "--close",
                                "--browser", "Google Chrome"])
            self.assertEqual(win.call_count, 1)
            close.assert_not_called()
            self.assertEqual(len(load_opened(log)), 3)


if __name__ == "__main__":
    unittest.main()
