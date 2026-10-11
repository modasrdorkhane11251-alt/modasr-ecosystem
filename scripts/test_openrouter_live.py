#!/usr/bin/env python3
"""
تست زنده‌ی OpenRouter: فقط یک درخواست آزمایشی می‌فرستد، نتیجه را کوتاه چاپ می‌کند.

⚠️ OpenRouter ارائه‌دهنده‌ی اصلی فعلی پروژه است. برای تست Gemini (غیرفعال/اختیاری)
از scripts/test_gemini_live.py استفاده کنید.
هیچ‌جا کلید API چاپ نمی‌شود — حتی در پیام خطا.

اجرا:
    cd modasr-ecosystem
    cp .env.example .env   # و OPENROUTER_API_KEY را پر کنید
    python3 scripts/test_openrouter_live.py

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
from openrouter import OpenRouterClient, OpenRouterConfig, OpenRouterError  # noqa: E402


def mask(key: str) -> str:
    """فقط برای تایید اینکه *یک* کلید بارگذاری شده، نه خودش. هیچ‌جای دیگر این فایل کلید چاپ نمی‌شود."""
    if not key:
        return "(خالی)"
    return f"{key[:3]}…{key[-2:]} (طول {len(key)})"


def main() -> int:
    cfg = AppConfig.load()
    missing = cfg.problems(["openrouter_api_key"])
    if missing:
        print("❌ پیکربندی ناقص:")
        for m in missing:
            print(" -", m)
        return 1

    print(f"کلید بارگذاری شد: {mask(cfg.openrouter_api_key)}")
    print(f"مدل: {cfg.openrouter_model}")
    print("در حال ارسال یک درخواست آزمایشی...")

    client = OpenRouterClient(OpenRouterConfig(
        api_key=cfg.openrouter_api_key, model=cfg.openrouter_model,
        timeout_s=cfg.openrouter_timeout_s, max_retries=cfg.openrouter_max_retries,
        http_referer=cfg.openrouter_http_referer,
    ))
    try:
        reply = client.generate(
            history=[],
            prompt="فقط دقیقاً همین یک کلمه را به فارسی جواب بده: سلام",
            system_instruction="خیلی کوتاه پاسخ بده.",
        )
    except OpenRouterError as e:
        print(f"❌ ناموفق: {e.user_message}")
        print(f"   (جزئیات فنی برای لاگ سرور، نه برای کاربر نهایی: {e.technical_detail[:200]})")
        return 2

    print("✅ موفق. پاسخ مدل:")
    print(" ", reply.strip()[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
