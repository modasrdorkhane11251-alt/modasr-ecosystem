"""
لایه‌ی دسترسی به داده: SQLite با مهاجرت نسخه‌دار (بدون تغییر مخرب شِما).

هویت کاربر به‌صورت (platform, platform_user_id) ذخیره می‌شود تا یک نفر بتواند هم از
تلگرام و هم از بله استفاده کند بدون اینکه فرض شود این‌ها "همان حساب" هستند؛
اتصال صریح حساب‌ها (account linking) بعداً و با تایید دوطرفه اضافه می‌شود، نه خودکار.
"""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass

SCHEMA_VERSION = 1

_MIGRATIONS: dict[int, list[str]] = {
    1: [
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            platform_user_id TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            UNIQUE(platform, platform_user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user','model')),
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, created_at)",
        """CREATE TABLE IF NOT EXISTS usage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            feature TEXT NOT NULL,
            day TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, feature, day)
        )""",
    ],
}


@dataclass
class User:
    id: int
    platform: str
    platform_user_id: str
    display_name: str
    created_at: float


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        cur = self._conn.execute("PRAGMA user_version")
        current = cur.fetchone()[0]
        for version in range(current + 1, SCHEMA_VERSION + 1):
            for stmt in _MIGRATIONS.get(version, []):
                self._conn.execute(stmt)
            self._conn.execute(f"PRAGMA user_version = {version}")
        self._conn.commit()

    @contextmanager
    def tx(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()

    # ---- کاربران ---------------------------------------------------
    def get_or_create_user(self, platform: str, platform_user_id: str, display_name: str = "") -> User:
        with self.tx() as c:
            row = c.execute(
                "SELECT * FROM users WHERE platform=? AND platform_user_id=?",
                (platform, str(platform_user_id)),
            ).fetchone()
            if row is None:
                c.execute(
                    "INSERT INTO users (platform, platform_user_id, display_name, created_at) VALUES (?,?,?,?)",
                    (platform, str(platform_user_id), display_name, time.time()),
                )
                row = c.execute(
                    "SELECT * FROM users WHERE platform=? AND platform_user_id=?",
                    (platform, str(platform_user_id)),
                ).fetchone()
            elif display_name and display_name != row["display_name"]:
                c.execute("UPDATE users SET display_name=? WHERE id=?", (display_name, row["id"]))
                row = c.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
        return User(**dict(row))

    # ---- مکالمه (برای حافظه‌ی Gemini) -------------------------------
    def append_message(self, user_id: int, role: str, content: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO conversations (user_id, role, content, created_at) VALUES (?,?,?,?)",
                (user_id, role, content, time.time()),
            )

    def recent_messages(self, user_id: int, limit: int) -> list[tuple[str, str]]:
        rows = self._conn.execute(
            "SELECT role, content FROM conversations WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [(r["role"], r["content"]) for r in reversed(rows)]

    def clear_conversation(self, user_id: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM conversations WHERE user_id=?", (user_id,))

    # ---- مصرف روزانه --------------------------------------------------
    def increment_usage(self, user_id: int, feature: str, day: str) -> int:
        with self.tx() as c:
            c.execute(
                """INSERT INTO usage_records (user_id, feature, day, count) VALUES (?,?,?,1)
                   ON CONFLICT(user_id, feature, day) DO UPDATE SET count = count + 1""",
                (user_id, feature, day),
            )
            row = c.execute(
                "SELECT count FROM usage_records WHERE user_id=? AND feature=? AND day=?",
                (user_id, feature, day),
            ).fetchone()
        return row["count"]

    def get_usage(self, user_id: int, feature: str, day: str) -> int:
        row = self._conn.execute(
            "SELECT count FROM usage_records WHERE user_id=? AND feature=? AND day=?",
            (user_id, feature, day),
        ).fetchone()
        return row["count"] if row else 0
