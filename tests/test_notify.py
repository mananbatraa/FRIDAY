"""Phone notifications through ntfy, with buttons that text FRIDAY back."""
import json
import os
import unittest
from unittest import mock

from tracker import notify
from tracker.notify import button, buttons


class ButtonsTest(unittest.TestCase):
    def test_standard_buttons(self):
        with mock.patch.dict(os.environ, {"NTFY_INBOX_TOPIC": "in-abc"}):
            labels = [b["label"] for b in buttons()]
            self.assertEqual(labels, ["List", "Pending", "Message FRIDAY"])
            self.assertEqual(button("Done", "done HW3"), {
                "action": "http", "label": "Done", "url": "https://ntfy.sh/in-abc", "method": "POST",
                "body": "done HW3", "clear": True})

    def test_an_extra_button_comes_first_and_typing_stays(self):
        with mock.patch.dict(os.environ, {"NTFY_INBOX_TOPIC": "in-abc"}):
            labels = [b["label"] for b in buttons([button("Done", "done HW3")])]
        self.assertEqual(labels, ["Done", "List", "Message FRIDAY"])

    def test_no_inbox_no_buttons(self):
        with mock.patch.dict(os.environ, {"NTFY_INBOX_TOPIC": ""}):
            self.assertEqual(buttons([button("Done", "done HW3")]), [])

    def test_sent_as_json(self):
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        with mock.patch.dict(os.environ, {"NTFY_INBOX_TOPIC": "in-abc"}), \
                mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            notify.send_ntfy("out-abc", "FRIDAY: coming up — HW3", "HW3: due in 30 min")
        sent = json.loads(urlopen.call_args[0][0].data)
        self.assertEqual((sent["topic"], sent["title"]), ("out-abc", "FRIDAY: coming up — HW3"))
        self.assertEqual(len(sent["actions"]), 3)


if __name__ == "__main__":
    unittest.main()
