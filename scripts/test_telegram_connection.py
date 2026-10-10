#!/usr/bin/env python3
"""
تست زنده‌ی اتصال تلگرام: فقط getMe می‌زند. هیچ پیامی به هیچ‌کس ارسال نمی‌شود.
توکن هیچ‌جا چاپ نمی‌شود.

اجرا:
    cd modasr-ecosystem
    cp .env.example .env   # و BOT_TOKEN را پر کنید
    python3 scripts/test_telegram_connection.py

کد خروج: 0 = متصل، 1 = پیکربندی ناقص، 2 = اتصال ناموفق.
"""
from __future__ import annotations

import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "packages" / "core"
TG = Path(__file__).resolve().parents[1] / "apps" / "telegram-bot"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(TG))

from config import AppConfig  # noqa: E402
from adapter import TelegramAdapter  # noqa: E402


def main() -> int:
    cfg = AppConfig.load()
    missing = cfg.problems(["telegram_bot_token"])
    if missing:
        print("❌ پیکربندی ناقص:")
        for m in missing:
            print(" -", m)
        return 1

    print(f"توکن بارگذاری شد (طول {len(cfg.telegram_bot_token)} کاراکتر؛ خود توکن چاپ نمی‌شود).")
    print("در حال فراخوانی getMe...")
    adapter = TelegramAdapter(cfg.telegram_bot_token)
    health = adapter.health_check()
    if health.ok:
        print(f"✅ متصل. {health.detail}")
        return 0
    print(f"❌ اتصال ناموفق: {health.detail}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
