import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core"))
from config import AppConfig, _load_dotenv_if_present  # noqa: E402


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._saved = dict(os.environ)
        for k in list(os.environ):
            if k in ("GEMINI_API_KEY", "BOT_TOKEN", "BALE_BOT_TOKEN", "ADMIN_ID", "DB_PATH"):
                del os.environ[k]

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def test_defaults_when_env_empty(self):
        cfg = AppConfig()
        self.assertEqual(cfg.gemini_model, "gemini-2.5-flash")
        self.assertEqual(cfg.db_path, "data/modasr.db")
        self.assertEqual(cfg.gemini_api_key, "")

    def test_reads_from_environment(self):
        os.environ["GEMINI_API_KEY"] = "abc123"
        os.environ["ADMIN_ID"] = "9991"
        cfg = AppConfig()
        self.assertEqual(cfg.gemini_api_key, "abc123")
        self.assertEqual(cfg.telegram_admin_id, 9991)

    def test_admin_id_falls_back_on_bad_int(self):
        os.environ["ADMIN_ID"] = "not-a-number"
        cfg = AppConfig()
        self.assertEqual(cfg.telegram_admin_id, 0)

    def test_problems_reports_missing_required_fields(self):
        cfg = AppConfig()
        issues = cfg.problems(["gemini_api_key", "telegram_bot_token"])
        self.assertEqual(len(issues), 2)

    def test_problems_empty_when_all_set(self):
        os.environ["GEMINI_API_KEY"] = "x"
        cfg = AppConfig()
        issues = cfg.problems(["gemini_api_key"])
        self.assertEqual(issues, [])

    def test_dotenv_file_is_loaded_without_overwriting_existing_env(self):
        os.environ["BOT_TOKEN"] = "from-real-env"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text('GEMINI_API_KEY=from-dotenv\nBOT_TOKEN=should-not-override\n# comment\n\n')
            cwd = os.getcwd()
            os.chdir(d)
            try:
                _load_dotenv_if_present(".env")
            finally:
                os.chdir(cwd)
        self.assertEqual(os.environ["GEMINI_API_KEY"], "from-dotenv")
        self.assertEqual(os.environ["BOT_TOKEN"], "from-real-env")  # محیط واقعی اولویت دارد


if __name__ == "__main__":
    unittest.main()
