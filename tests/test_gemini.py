import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core"))
from ai.gemini import GeminiClient, GeminiConfig, GeminiError  # noqa: E402


def make_response(status_code, json_data=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.text = text or str(json_data)
    return r


def success_payload(text="سلام، چطور می‌توانم کمک کنم؟"):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class GeminiClientTests(unittest.TestCase):
    def setUp(self):
        self.cfg = GeminiConfig(api_key="test-key", max_retries=2, retry_base_delay_s=0)
        self.sleeps = []

    def _client(self, session):
        return GeminiClient(self.cfg, session=session, sleep_fn=lambda s: self.sleeps.append(s))

    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            GeminiClient(GeminiConfig(api_key=""))

    def test_successful_response_returns_text(self):
        session = MagicMock()
        session.post.return_value = make_response(200, success_payload("پاسخ تست"))
        client = self._client(session)
        result = client.generate(history=[], prompt="سلام")
        self.assertEqual(result, "پاسخ تست")
        self.assertEqual(session.post.call_count, 1)

    def test_sends_history_and_system_instruction_correctly(self):
        session = MagicMock()
        session.post.return_value = make_response(200, success_payload())
        client = self._client(session)
        client.generate(history=[("user", "قبلی"), ("model", "جواب قبلی")],
                        prompt="الان", system_instruction="تو یک دستیار مودبی.")
        _, kwargs = session.post.call_args
        payload = kwargs["json"]
        self.assertEqual(len(payload["contents"]), 3)
        self.assertEqual(payload["contents"][-1]["parts"][0]["text"], "الان")
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "تو یک دستیار مودبی.")
        self.assertEqual(kwargs["headers"]["X-goog-api-key"], "test-key")

    def test_401_raises_immediately_without_retry(self):
        session = MagicMock()
        session.post.return_value = make_response(401, text="API key invalid")
        client = self._client(session)
        with self.assertRaises(GeminiError) as ctx:
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, 1)
        self.assertIn("کلید API", ctx.exception.user_message)
        self.assertNotIn("API key invalid", ctx.exception.user_message)  # جزییات فنی لو نرود

    def test_400_raises_immediately(self):
        session = MagicMock()
        session.post.return_value = make_response(400)
        client = self._client(session)
        with self.assertRaises(GeminiError):
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, 1)

    def test_404_model_not_found_raises_immediately(self):
        session = MagicMock()
        session.post.return_value = make_response(404)
        client = self._client(session)
        with self.assertRaises(GeminiError) as ctx:
            client.generate(history=[], prompt="hi")
        self.assertIn("مدل", ctx.exception.user_message)

    def test_429_retries_then_succeeds(self):
        session = MagicMock()
        session.post.side_effect = [make_response(429), make_response(200, success_payload("ok"))]
        client = self._client(session)
        result = client.generate(history=[], prompt="hi")
        self.assertEqual(result, "ok")
        self.assertEqual(session.post.call_count, 2)
        self.assertEqual(len(self.sleeps), 1)

    def test_503_retries_until_exhausted_then_raises(self):
        session = MagicMock()
        session.post.return_value = make_response(503)
        client = self._client(session)
        with self.assertRaises(GeminiError):
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, self.cfg.max_retries + 1)

    def test_timeout_retries_then_raises(self):
        import requests
        session = MagicMock()
        session.post.side_effect = requests.Timeout()
        client = self._client(session)
        with self.assertRaises(GeminiError) as ctx:
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, self.cfg.max_retries + 1)
        self.assertIn("timeout", ctx.exception.technical_detail)

    def test_blocked_prompt_raises_clear_error(self):
        session = MagicMock()
        session.post.return_value = make_response(200, {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}})
        client = self._client(session)
        with self.assertRaises(GeminiError) as ctx:
            client.generate(history=[], prompt="hi")
        self.assertIn("SAFETY", ctx.exception.user_message)


if __name__ == "__main__":
    unittest.main()
