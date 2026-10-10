import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("bale_adapter_module", Path(__file__).resolve().parents[1] / "apps" / "bale-bot" / "adapter.py")
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
BaleAdapter = _mod.BaleAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core"))
from platform_adapter import MediaKind  # noqa: E402


def resp(json_data):
    r = MagicMock()
    r.json.return_value = json_data
    r.status_code = 200
    return r


class BaleAdapterTests(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.adapter = BaleAdapter("123:fake-token", session=self.session)

    def test_requires_token(self):
        with self.assertRaises(ValueError):
            BaleAdapter("")

    def test_parse_text_message(self):
        raw = {"message": {"chat": {"id": 555}, "from": {"id": 10, "first_name": "Ali"}, "text": "سلام"}}
        msg = self.adapter.parse_update(raw)
        self.assertEqual(msg.chat_id, "555")
        self.assertEqual(msg.user_id, "10")
        self.assertEqual(msg.text, "سلام")
        self.assertIsNone(msg.media_kind)
        self.assertEqual(msg.platform, "bale")

    def test_parse_photo_message_takes_largest_size(self):
        raw = {"message": {"chat": {"id": 1}, "from": {"id": 2}, "caption": "ببین",
                           "photo": [{"file_id": "small"}, {"file_id": "big"}]}}
        msg = self.adapter.parse_update(raw)
        self.assertEqual(msg.media_kind, MediaKind.PHOTO)
        self.assertEqual(msg.media_file_id, "big")
        self.assertEqual(msg.caption, "ببین")

    def test_parse_voice_message(self):
        raw = {"message": {"chat": {"id": 1}, "from": {"id": 2}, "voice": {"file_id": "v1"}}}
        msg = self.adapter.parse_update(raw)
        self.assertEqual(msg.media_kind, MediaKind.VOICE)
        self.assertEqual(msg.media_file_id, "v1")

    def test_parse_callback_query(self):
        raw = {"callback_query": {"data": "dl|v|abc", "from": {"id": 2, "first_name": "A"},
                                  "message": {"chat": {"id": 1}}}}
        msg = self.adapter.parse_update(raw)
        self.assertEqual(msg.callback_data, "dl|v|abc")
        self.assertEqual(msg.chat_id, "1")

    def test_parse_update_with_no_message_returns_none(self):
        self.assertIsNone(self.adapter.parse_update({"some_other_field": {}}))

    def test_send_text_success(self):
        self.session.post.return_value = resp({"ok": True, "result": {"message_id": 99}})
        result = self.adapter.send_text("1", "سلام")
        self.assertTrue(result.ok)
        self.assertEqual(result.message_id, "99")

    def test_send_text_failure_returns_error_not_exception(self):
        self.session.post.return_value = resp({"ok": False, "description": "chat not found"})
        result = self.adapter.send_text("1", "سلام")
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "chat not found")

    def test_send_text_truncates_long_text(self):
        self.session.post.return_value = resp({"ok": True, "result": {"message_id": 1}})
        self.adapter.send_text("1", "a" * 5000)
        sent_text = self.session.post.call_args.kwargs["json"]["text"]
        self.assertEqual(len(sent_text), 4096)

    def test_health_check_ok(self):
        self.session.get.return_value = resp({"ok": True, "result": {"username": "mybot"}})
        h = self.adapter.health_check()
        self.assertTrue(h.ok)
        self.assertIn("mybot", h.detail)

    def test_health_check_network_failure(self):
        import requests
        self.session.get.side_effect = requests.ConnectionError("dns fail")
        h = self.adapter.health_check()
        self.assertFalse(h.ok)


if __name__ == "__main__":
    unittest.main()
