#!/usr/bin/env python3
"""
تست زنده‌ی Gemini: فقط یک درخواست آزمایشی می‌فرستد، نتیجه را کوتاه چاپ می‌کند.
هیچ‌جا کلید API چاپ نمی‌شود — حتی در پیام خطا.

اجرا:
    cd modasr-ecosystem
    cp .env.example .env   # و GEMINI_API_KEY را پر کنید
    python3 scripts/test_gemini_live.py

خروجی: یا "✅ موفق" با پاسخ مدل، یا "❌ ناموفق" با پیام خطای ایمن (بدون کلید/جزئیات خام).
کد خروج: 0 = موفق، 1 = پیکربندی ناقص، 2 = خطای زمان اجرا (شبکه/API).
"""
from __future__ import annotations

import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "packages" / "core"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(CORE / "ai"))

from config import AppConfig  # noqa: E402
from gemini import GeminiClient, GeminiConfig, GeminiError  # noqa: E402


def mask(key: str) -> str:
    """فقط برای تایید اینکه *یک* کلید بارگذاری شده، نه خودش. هیچ‌جای دیگر این فایل کلید چاپ نمی‌شود."""
    if not key:
        return "(خالی)"
    return f"{key[:3]}…{key[-2:]} (طول {len(key)})"


def main() -> int:
    cfg = AppConfig.load()
    missing = cfg.problems(["gemini_api_key"])
    if missing:
        print("❌ پیکربندی ناقص:")
        for m in missing:
            print(" -", m)
        return 1

    print(f"کلید بارگذاری شد: {mask(cfg.gemini_api_key)}")
    print(f"مدل: {cfg.gemini_model}")
    print("در حال ارسال یک درخواست آزمایشی...")

    client = GeminiClient(GeminiConfig(
        api_key=cfg.gemini_api_key, model=cfg.gemini_model,
        timeout_s=cfg.gemini_timeout_s, max_retries=cfg.gemini_max_retries,
    ))
    try:
        reply = client.generate(
            history=[],
            prompt="فقط دقیقاً همین یک کلمه را به فارسی جواب بده: سلام",
            system_instruction="خیلی کوتاه پاسخ بده.",
        )
    except GeminiError as e:
        print(f"❌ ناموفق: {e.user_message}")
        print(f"   (جزئیات فنی برای لاگ سرور، نه برای کاربر نهایی: {e.technical_detail[:200]})")
        return 2

    print("✅ موفق. پاسخ مدل:")
    print(" ", reply.strip()[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
