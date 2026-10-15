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

SCHEMA_VERSION = 2

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
    2: [
        # اشتراک/لایسنس — فقط «manual entitlement» (صدور دستی توسط ادمین)؛ هیچ درگاه
        # پرداخت واقعی اینجا نیست. هر کاربر در هر لحظه حداکثر یک ردیف اشتراک فعال دارد؛
        # تمدید = آپدیت همین ردیف (تاریخچه در subscription_audit_log ثبت می‌شود).
        """CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            plan TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('active','revoked','expired')),
            granted_at REAL NOT NULL,
            expires_at REAL,
            granted_by TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS subscription_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            action TEXT NOT NULL CHECK(action IN ('grant','renew','revoke')),
            plan TEXT NOT NULL,
            performed_by TEXT NOT NULL,
            performed_at REAL NOT NULL,
            note TEXT NOT NULL DEFAULT ''
        )""",
        "CREATE INDEX IF NOT EXISTS idx_sub_audit_user ON subscription_audit_log(user_id, performed_at)",
    ],
}

# پلن‌های اشتراک: فقط تعریف نام/مدت/محدودیت روزانه؛ قیمت‌گذاری و پرداخت واقعی بعداً،
# وقتی یک درگاه واقعی انتخاب و تایید شد (طبق تصمیم صریح پروژه، هنوز نه).
SUBSCRIPTION_PLANS: dict[str, dict] = {
    "free":      {"label": "رایگان",            "days": None, "daily_chat_limit": 20},
    "monthly":   {"label": "ماهانه",            "days": 30,   "daily_chat_limit": None},
    "quarterly": {"label": "سه‌ماهه",            "days": 90,   "daily_chat_limit": None},
    "biannual":  {"label": "شش‌ماهه",            "days": 182,  "daily_chat_limit": None},
    "yearly":    {"label": "یک‌ساله",            "days": 365,  "daily_chat_limit": None},
    "lifetime":  {"label": "دائمی (Perpetual)", "days": None, "daily_chat_limit": None},
}


@dataclass
class User:
    id: int
    platform: str
    platform_user_id: str
    display_name: str
    created_at: float


@dataclass
class Subscription:
    user_id: int
    plan: str
    status: str  # 'active' | 'revoked' | 'expired'
    granted_at: float
    expires_at: float | None
    granted_by: str
    note: str

    def is_active_now(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        if self.status != "active":
            return False
        return self.expires_at is None or self.expires_at > now


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

    # ---- اشتراک/لایسنس (manual entitlement؛ بدون درگاه پرداخت واقعی) ----------
    def grant_subscription(self, user_id: int, plan: str, granted_by: str, note: str = "") -> Subscription:
        """اگر پلن نامعتبر باشد ValueError می‌دهد. اگر کاربر از قبل اشتراک داشته باشد،
        ردیفش آپدیت می‌شود (تمدید/تغییر پلن)، نه یک ردیف جدید؛ اما در audit_log هر
        فراخوانی یک ردیف جدید ثبت می‌کند (تاریخچه هیچ‌وقت پاک نمی‌شود)."""
        if plan not in SUBSCRIPTION_PLANS:
            raise ValueError(f"پلن نامعتبر: {plan}")
        days = SUBSCRIPTION_PLANS[plan]["days"]
        now = time.time()
        expires_at = (now + days * 86400) if days else None
        action = "renew" if self.get_subscription(user_id) else "grant"
        with self.tx() as c:
            c.execute(
                """INSERT INTO subscriptions (user_id, plan, status, granted_at, expires_at, granted_by, note)
                   VALUES (?, ?, 'active', ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     plan=excluded.plan, status='active', granted_at=excluded.granted_at,
                     expires_at=excluded.expires_at, granted_by=excluded.granted_by, note=excluded.note""",
                (user_id, plan, now, expires_at, granted_by, note),
            )
            c.execute(
                """INSERT INTO subscription_audit_log (user_id, action, plan, performed_by, performed_at, note)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, action, plan, granted_by, now, note),
            )
        return self.get_subscription(user_id)

    def revoke_subscription(self, user_id: int, performed_by: str, note: str = "") -> None:
        existing = self.get_subscription(user_id)
        if not existing:
            return  # چیزی برای لغو نیست؛ سکوت امن‌تر از خطا برای این عملیات idempotent است
        now = time.time()
        with self.tx() as c:
            c.execute("UPDATE subscriptions SET status='revoked', note=? WHERE user_id=?", (note, user_id))
            c.execute(
                """INSERT INTO subscription_audit_log (user_id, action, plan, performed_by, performed_at, note)
                   VALUES (?, 'revoke', ?, ?, ?, ?)""",
                (user_id, existing.plan, performed_by, now, note),
            )

    def get_subscription(self, user_id: int) -> Subscription | None:
        row = self._conn.execute("SELECT * FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
        return Subscription(**dict(row)) if row else None

    def is_subscription_active(self, user_id: int) -> bool:
        sub = self.get_subscription(user_id)
        return sub is not None and sub.is_active_now()

    def subscription_audit_log(self, user_id: int, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM subscription_audit_log WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_subscriptions(self, status: str | None = None, limit: int = 200) -> list[Subscription]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM subscriptions WHERE status=? ORDER BY granted_at DESC LIMIT ?", (status, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM subscriptions ORDER BY granted_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Subscription(**dict(r)) for r in rows]
