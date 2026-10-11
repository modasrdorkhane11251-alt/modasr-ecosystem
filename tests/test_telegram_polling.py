import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core" / "ai"))

os.environ.setdefault("BOT_TOKEN", "123:fake")
os.environ.setdefault("OPENROUTER_API_KEY", "fake-key")

import importlib.util as _ilu
_app_dir = Path(__file__).resolve().parents[1] / "apps" / "telegram-bot"
_spec = _ilu.spec_from_file_location("telegram_bot_main_module", _app_dir / "main.py")
M = _ilu.module_from_spec(_spec)
sys.modules[_spec.name] = M  # قبل از exec، تا import داخلی main.py (adapter) هم پیدا شود
sys.path.insert(0, str(_app_dir))
# main.py داخلش "from adapter import X" با نام ساده می‌زند؛ چون تلگرام و بله هر دو یک
# فایل به اسم adapter.py دارند، کش sys.modules["adapter"] بین این دو تداخل می‌کند.
# برای همین قبل و بعد از اجرا پاکش می‌کنیم (کلاس واقعی را از M.*Adapter برمی‌داریم، نه از سراسری).
sys.modules.pop("adapter", None)
_spec.loader.exec_module(M)
sys.modules.pop("adapter", None)
sys.path.pop(0)

from database import Database  # noqa: E402
TelegramAdapter = M.TelegramAdapter  # همان کلاسی که main.py استفاده می‌کند؛ تست و اجرا از یک ماژول


def fake_resp(status_code=200, json_data=None, text="", raise_json_error=False):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    if raise_json_error:
        r.json.side_effect = ValueError("invalid json")
    else:
        r.json.return_value = json_data
    return r


class PollOnceTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.gemini = MagicMock()
        self.adapter = TelegramAdapter("123:fake")
        self.adapter.send_text = MagicMock()

    def test_network_exception_does_not_crash_and_keeps_offset(self):
        import requests
        with patch.object(M, "requests", create=True), \
             patch("requests.get", side_effect=requests.ConnectionError("dns fail")):
            new_offset = M.poll_once(self.db, self.gemini, self.adapter, offset=10)
        self.assertEqual(new_offset, 10)

    def test_http_500_does_not_crash_and_keeps_offset(self):
        with patch("requests.get", return_value=fake_resp(status_code=500, text="Internal Server Error")):
            new_offset = M.poll_once(self.db, self.gemini, self.adapter, offset=5)
        self.assertEqual(new_offset, 5)

    def test_invalid_json_does_not_crash(self):
        with patch("requests.get", return_value=fake_resp(status_code=200, raise_json_error=True, text="<html>not json</html>")):
            new_offset = M.poll_once(self.db, self.gemini, self.adapter, offset=7)
        self.assertEqual(new_offset, 7)

    def test_ok_false_response_does_not_crash(self):
        with patch("requests.get", return_value=fake_resp(200, {"ok": False, "description": "Unauthorized"})):
            new_offset = M.poll_once(self.db, self.gemini, self.adapter, offset=3)
        self.assertEqual(new_offset, 3)

    def test_missing_result_field_does_not_crash(self):
        with patch("requests.get", return_value=fake_resp(200, {"ok": True})):
            new_offset = M.poll_once(self.db, self.gemini, self.adapter, offset=1)
        self.assertEqual(new_offset, 1)

    def test_update_without_update_id_is_skipped_safely(self):
        payload = {"ok": True, "result": [{"message": {"chat": {"id": 1}, "from": {"id": 2}, "text": "hi"}}]}
        with patch("requests.get", return_value=fake_resp(200, payload)):
            new_offset = M.poll_once(self.db, self.gemini, self.adapter, offset=None)
        self.assertIsNone(new_offset)  # offset عوض نشد چون update_id نداشت

    def test_successful_update_advances_offset_and_calls_handler(self):
        payload = {"ok": True, "result": [
            {"update_id": 100, "message": {"chat": {"id": 1}, "from": {"id": 2}, "text": "سلام"}}
        ]}
        self.gemini.generate.return_value = "پاسخ آزمایشی"
        with patch("requests.get", return_value=fake_resp(200, payload)):
            new_offset = M.poll_once(self.db, self.gemini, self.adapter, offset=None)
        self.assertEqual(new_offset, 101)
        self.adapter.send_text.assert_called_once()
        self.assertEqual(self.adapter.send_text.call_args.args[1], "پاسخ آزمایشی")

    def test_malformed_update_in_list_is_skipped_not_fatal(self):
        """یک آپدیت خراب نباید جلوی پردازش بقیه‌ی آپدیت‌های همان دسته را بگیرد."""
        payload = {"ok": True, "result": [
            {"update_id": 1, "message": {"chat": None}},  # خراب: chat=None باعث AttributeError در parse می‌شود؟
            {"update_id": 2, "message": {"chat": {"id": 9}, "from": {"id": 8}, "text": "ok"}},
        ]}
        self.gemini.generate.return_value = "پاسخ"
        with patch("requests.get", return_value=fake_resp(200, payload)):
            new_offset = M.poll_once(self.db, self.gemini, self.adapter, offset=None)
        self.assertEqual(new_offset, 3)
        self.adapter.send_text.assert_called_once()  # فقط برای آپدیت دوم


if __name__ == "__main__":
    unittest.main()
