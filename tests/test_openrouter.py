import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core"))
from ai.openrouter import OpenRouterClient, OpenRouterConfig, OpenRouterError  # noqa: E402


def make_response(status_code, json_data=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.text = text or str(json_data)
    return r


def success_payload(text="سلام، چطور می‌توانم کمک کنم؟"):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


class OpenRouterClientTests(unittest.TestCase):
    def setUp(self):
        self.cfg = OpenRouterConfig(api_key="test-key", max_retries=2, retry_base_delay_s=0)
        self.sleeps = []

    def _client(self, session):
        return OpenRouterClient(self.cfg, session=session, sleep_fn=lambda s: self.sleeps.append(s))

    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            OpenRouterClient(OpenRouterConfig(api_key=""))

    def test_successful_response_returns_text(self):
        session = MagicMock()
        session.post.return_value = make_response(200, success_payload("پاسخ تست"))
        client = self._client(session)
        result = client.generate(history=[], prompt="سلام")
        self.assertEqual(result, "پاسخ تست")
        self.assertEqual(session.post.call_count, 1)

    def test_sends_messages_in_openai_format_with_history_and_system(self):
        session = MagicMock()
        session.post.return_value = make_response(200, success_payload())
        client = self._client(session)
        client.generate(history=[("user", "قبلی"), ("model", "جواب قبلی")],
                        prompt="الان", system_instruction="تو یک دستیار مودبی.")
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], self.cfg.base_url)
        payload = kwargs["json"]
        self.assertEqual(payload["model"], self.cfg.model)
        msgs = payload["messages"]
        self.assertEqual(msgs[0], {"role": "system", "content": "تو یک دستیار مودبی."})
        self.assertEqual(msgs[1], {"role": "user", "content": "قبلی"})
        self.assertEqual(msgs[2], {"role": "assistant", "content": "جواب قبلی"})
        self.assertEqual(msgs[3], {"role": "user", "content": "الان"})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_no_system_message_when_instruction_empty(self):
        session = MagicMock()
        session.post.return_value = make_response(200, success_payload())
        client = self._client(session)
        client.generate(history=[], prompt="سلام")
        msgs = session.post.call_args.kwargs["json"]["messages"]
        self.assertEqual(msgs, [{"role": "user", "content": "سلام"}])

    def test_optional_headers_included_when_configured(self):
        session = MagicMock()
        session.post.return_value = make_response(200, success_payload())
        cfg = OpenRouterConfig(api_key="k", http_referer="https://example.com", app_title="MyApp",
                               max_retries=0)
        client = OpenRouterClient(cfg, session=session)
        client.generate(history=[], prompt="hi")
        headers = session.post.call_args.kwargs["headers"]
        self.assertEqual(headers["HTTP-Referer"], "https://example.com")
        self.assertEqual(headers["X-Title"], "MyApp")

    def test_401_raises_immediately_without_retry(self):
        session = MagicMock()
        session.post.return_value = make_response(401, text="invalid api key")
        client = self._client(session)
        with self.assertRaises(OpenRouterError) as ctx:
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, 1)
        self.assertIn("کلید API", ctx.exception.user_message)
        self.assertNotIn("invalid api key", ctx.exception.user_message)

    def test_400_raises_immediately(self):
        session = MagicMock()
        session.post.return_value = make_response(400)
        client = self._client(session)
        with self.assertRaises(OpenRouterError):
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, 1)

    def test_403_raises_immediately(self):
        session = MagicMock()
        session.post.return_value = make_response(403)
        client = self._client(session)
        with self.assertRaises(OpenRouterError):
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, 1)

    def test_404_model_not_found_raises_immediately(self):
        session = MagicMock()
        session.post.return_value = make_response(404)
        client = self._client(session)
        with self.assertRaises(OpenRouterError) as ctx:
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
        with self.assertRaises(OpenRouterError):
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, self.cfg.max_retries + 1)

    def test_timeout_retries_then_raises(self):
        import requests
        session = MagicMock()
        session.post.side_effect = requests.Timeout()
        client = self._client(session)
        with self.assertRaises(OpenRouterError) as ctx:
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, self.cfg.max_retries + 1)
        self.assertIn("timeout", ctx.exception.technical_detail)

    def test_network_exception_retries_then_raises(self):
        import requests
        session = MagicMock()
        session.post.side_effect = requests.ConnectionError("dns fail")
        client = self._client(session)
        with self.assertRaises(OpenRouterError) as ctx:
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, self.cfg.max_retries + 1)
        self.assertIn("network", ctx.exception.technical_detail)

    def test_empty_choices_raises_clear_error(self):
        session = MagicMock()
        session.post.return_value = make_response(200, {"choices": []})
        client = self._client(session)
        with self.assertRaises(OpenRouterError):
            client.generate(history=[], prompt="hi")

    def test_choices_with_empty_content_raises(self):
        session = MagicMock()
        session.post.return_value = make_response(200, {"choices": [{"message": {"content": ""}}]})
        client = self._client(session)
        with self.assertRaises(OpenRouterError):
            client.generate(history=[], prompt="hi")

    def test_invalid_json_response_raises_clear_error(self):
        session = MagicMock()
        r = MagicMock()
        r.status_code = 200
        r.json.side_effect = ValueError("not json")
        r.text = "<html>error page</html>"
        session.post.return_value = r
        client = self._client(session)
        with self.assertRaises(OpenRouterError):
            client.generate(history=[], prompt="hi")

    def test_unknown_status_code_raises_without_retry(self):
        session = MagicMock()
        session.post.return_value = make_response(418)
        client = self._client(session)
        with self.assertRaises(OpenRouterError):
            client.generate(history=[], prompt="hi")
        self.assertEqual(session.post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
