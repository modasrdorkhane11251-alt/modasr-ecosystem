import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core"))
from database import Database  # noqa: E402


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_get_or_create_user_is_idempotent(self):
        u1 = self.db.get_or_create_user("telegram", "111", "Ali")
        u2 = self.db.get_or_create_user("telegram", "111", "Ali")
        self.assertEqual(u1.id, u2.id)

    def test_same_platform_user_id_on_different_platforms_are_different_users(self):
        t = self.db.get_or_create_user("telegram", "111", "Ali")
        b = self.db.get_or_create_user("bale", "111", "Ali")
        self.assertNotEqual(t.id, b.id)

    def test_display_name_updates_on_change(self):
        u1 = self.db.get_or_create_user("telegram", "111", "Ali")
        u2 = self.db.get_or_create_user("telegram", "111", "Ali Reza")
        self.assertEqual(u1.id, u2.id)
        self.assertEqual(u2.display_name, "Ali Reza")

    def test_conversation_history_order_and_limit(self):
        u = self.db.get_or_create_user("telegram", "1", "A")
        for i in range(5):
            self.db.append_message(u.id, "user", f"msg{i}")
            self.db.append_message(u.id, "model", f"reply{i}")
        history = self.db.recent_messages(u.id, limit=4)
        self.assertEqual(len(history), 4)
        self.assertEqual(history, [("user", "msg3"), ("model", "reply3"),
                                    ("user", "msg4"), ("model", "reply4")])

    def test_clear_conversation(self):
        u = self.db.get_or_create_user("telegram", "1", "A")
        self.db.append_message(u.id, "user", "hi")
        self.db.clear_conversation(u.id)
        self.assertEqual(self.db.recent_messages(u.id, 10), [])

    def test_usage_increment_and_isolated_by_day_and_feature(self):
        u = self.db.get_or_create_user("telegram", "1", "A")
        self.assertEqual(self.db.increment_usage(u.id, "download", "2026-10-10"), 1)
        self.assertEqual(self.db.increment_usage(u.id, "download", "2026-10-10"), 2)
        self.assertEqual(self.db.get_usage(u.id, "download", "2026-10-11"), 0)
        self.assertEqual(self.db.get_usage(u.id, "music", "2026-10-10"), 0)

    def test_persists_across_reconnect_to_same_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = f"{d}/sub/test.db"
            db1 = Database(path)
            u = db1.get_or_create_user("telegram", "42", "Reza")
            db1.append_message(u.id, "user", "salam")
            db1.close()

            db2 = Database(path)
            u2 = db2.get_or_create_user("telegram", "42", "Reza")
            self.assertEqual(u.id, u2.id)
            self.assertEqual(db2.recent_messages(u2.id, 10), [("user", "salam")])
            db2.close()

    def test_migration_is_idempotent_on_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            path = f"{d}/test.db"
            Database(path).close()
            Database(path).close()  # نباید خطا بدهد یا جدول را دوباره بسازد و داده از دست برود


if __name__ == "__main__":
    unittest.main()
