"""The phone assistant: Claude Code with only FRIDAY's tools, and drafts that only you can send."""
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

from tracker import agent, tools

NOW = datetime(2026, 10, 31, 13, 0)


class CommandTest(unittest.TestCase):
    def test_only_friday_tools_and_the_web(self):
        args = agent.command("email Sam", None)
        self.assertEqual(args[args.index("--tools") + 1], "Bash,WebSearch,WebFetch")
        self.assertIn("Bash(.venv/bin/python -m tracker.tools:*)", args)
        self.assertEqual(args[args.index("--permission-mode") + 1], "dontAsk")
        self.assertIn("--strict-mcp-config", args)
        self.assertNotIn("--resume", args)
        self.assertEqual(agent.command("yes", "abc")[-2:], ["--resume", "abc"])
        self.assertEqual(args[args.index("--model") + 1], "sonnet")
        with mock.patch.dict(os.environ, {"FRIDAY_MODEL": "opus"}):
            self.assertIn("opus", agent.command("hi", None))


class AskTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(agent, "STATE_FILE", os.path.join(self.dir.name, "agent.json"))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.dir.cleanup()

    def run_ask(self, text, now, stdout):
        done = subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")
        with mock.patch("subprocess.run", return_value=done) as run:
            return agent.ask(text, now), run.call_args[0][0]

    def test_a_conversation_continues_for_30_minutes(self):
        reply, args = self.run_ask("email Sam", NOW, json.dumps({"result": "Who?", "session_id": "s1"}))
        self.assertEqual(reply, "Who?")
        self.assertNotIn("--resume", args)
        _, args = self.run_ask("Sam Lee", NOW + timedelta(minutes=5), json.dumps({"result": "ok", "session_id": "s1"}))
        self.assertEqual(args[-2:], ["--resume", "s1"])
        _, args = self.run_ask("hi", NOW + timedelta(hours=2), json.dumps({"result": "hi", "session_id": "s2"}))
        self.assertNotIn("--resume", args)

    def test_new_forgets(self):
        self.run_ask("email Sam", NOW, json.dumps({"result": "Who?", "session_id": "s1"}))
        agent.forget()
        _, args = self.run_ask("hi", NOW + timedelta(minutes=1), json.dumps({"result": "hi"}))
        self.assertNotIn("--resume", args)

    def test_not_logged_in(self):
        reply, _ = self.run_ask("hi", NOW, "Invalid API key · Please run /login")
        self.assertIn("Please run /login", reply)


class DraftTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(tools, "PENDING_FILE", os.path.join(self.dir.name, "pending.json"))
        self.patch.start()
        self.gmail = mock.MagicMock()
        self.gmail.users().drafts().create().execute.return_value = {"id": "d1"}
        self.service = mock.patch.object(tools, "_service", return_value=self.gmail)
        self.service.start()

    def tearDown(self):
        self.service.stop()
        self.patch.stop()
        self.dir.cleanup()

    def test_a_draft_waits_for_its_code(self):
        reply = tools.draft("sam@school.edu", "Slides", "Hi Sam")
        code = reply.split("code ")[1][:4]
        self.assertIn("Not sent", reply)
        self.gmail.users().drafts().send.assert_not_called()
        self.assertEqual(tools.send("0000"), "No draft waiting with code '0000'. Codes last a day.")
        self.assertEqual(tools.send(code), 'Sent "Slides" to sam@school.edu.')
        self.gmail.users().drafts().send.assert_called_with(userId="me", body={"id": "d1"})
        self.assertIn("No draft waiting", tools.send(code))  # only once

    def test_cancel_deletes_the_draft(self):
        code = tools.draft("a@b.com", "Hi", "x").split("code ")[1][:4]
        self.assertIn("Nothing was sent", tools.cancel(code))
        self.gmail.users().drafts().delete.assert_called_with(userId="me", id="d1")

    def test_a_revised_draft_replaces_the_old_one(self):
        old = tools.draft("a@b.com", "Hi", "long").split("code ")[1][:4]
        self.gmail.users().drafts().create().execute.return_value = {"id": "d2"}
        reply = tools.draft("a@b.com", "Hi", "short", cc="c@d.com", replaces=old)
        new = reply.split("code ")[1][:4]
        self.assertIn("replaced; nothing was sent", reply)
        self.gmail.users().drafts().delete.assert_called_with(userId="me", id="d1")
        self.assertEqual(list(tools.load_pending()), [new])

    def test_a_reply_goes_in_the_thread(self):
        self.gmail.users().messages().get().execute.return_value = {
            "threadId": "t9", "snippet": "Can you send the slides?",
            "payload": {"headers": [{"name": "From", "value": "Sam <sam@school.edu>"},
                                    {"name": "Subject", "value": "Slides"},
                                    {"name": "Message-ID", "value": "<m1@mail>"},
                                    {"name": "Date", "value": "Fri, 30 Oct 2026 19:00:00 -0700"}]}}
        with mock.patch.object(tools, "_accounts", return_value={"school": ("t", "c")}):
            reply = tools.draft("", "", "Sounds good!", reply_to="school:m1")
        self.assertIn('subject "Re: Slides"', reply)
        self.assertIn("Can you send the slides?", reply)
        body = self.gmail.users().drafts().create.call_args.kwargs["body"]["message"]
        self.assertEqual(body["threadId"], "t9")
        import base64
        raw = base64.urlsafe_b64decode(body["raw"]).decode()
        self.assertIn("In-Reply-To: <m1@mail>", raw)
        self.assertIn("To: Sam <sam@school.edu>", raw)

    def test_contacts_most_emailed_first(self):
        def headers(service, message_id, names):
            return {"From": "Alex Kim <alex@gmail.com>" if message_id == "1" else "Alex Kim <alex@school.edu>",
                    "snippet": ""}
        self.gmail.users().messages().list().execute.return_value = {"messages": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}
        with mock.patch.object(tools, "_accounts", return_value={"school": ("t", "c")}), \
                mock.patch.object(tools, "_headers", side_effect=headers):
            found = tools.contacts("alex")
        self.assertEqual(found, ["Alex Kim <alex@school.edu> (2 emails, in your school account)",
                                 "Alex Kim <alex@gmail.com> (1 email, in your school account)"])

    def test_the_assistant_cannot_send_through_ask(self):
        self.assertEqual(tools.main(["ask", "send 1234"]), 1)

    def test_apply_needs_a_link(self):
        self.assertEqual(tools.apply("rm -rf /"), "That isn't a web link.")


if __name__ == "__main__":
    unittest.main()
