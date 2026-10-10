"""
بارگذاری و اعتبارسنجی پیکربندی از متغیرهای محیطی.

اصل: هیچ کلید یا توکنی داخل کد نیست. هر چیزی که غایب باشد، در `AppConfig.problems()`
گزارش می‌شود (نه اینکه ساکت نادیده گرفته شود یا با مقدار پیش‌فرض خطرناک پر شود).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class AppConfig:
    # هسته
    db_path: str = field(default_factory=lambda: _env("DB_PATH", "data/modasr.db"))

    # Gemini
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: _env("GEMINI_MODEL", "gemini-2.5-flash"))
    gemini_timeout_s: int = field(default_factory=lambda: _env_int("GEMINI_TIMEOUT_S", 30))
    gemini_max_retries: int = field(default_factory=lambda: _env_int("GEMINI_MAX_RETRIES", 2))
    gemini_history_turns: int = field(default_factory=lambda: _env_int("GEMINI_HISTORY_TURNS", 8))

    # تلگرام
    telegram_bot_token: str = field(default_factory=lambda: _env("BOT_TOKEN"))
    telegram_admin_id: int = field(default_factory=lambda: _env_int("ADMIN_ID", 0))

    # بله
    bale_bot_token: str = field(default_factory=lambda: _env("BALE_BOT_TOKEN"))

    # روبیکا — عمداً هنوز اضافه نشده؛ به تصمیم کاربر درباره‌ی ریسک API غیررسمی بستگی دارد.

    def problems(self, required: list[str]) -> list[str]:
        """بررسی می‌کند کدام فیلدهای لازم برای این بخش از برنامه خالی مانده‌اند."""
        issues = []
        for field_name in required:
            if not getattr(self, field_name, ""):
                issues.append(f"{field_name} تنظیم نشده است (در .env)")
        return issues

    @classmethod
    def load(cls) -> "AppConfig":
        """مقادیر .env را (اگر فایل وجود داشته باشد) به os.environ اضافه می‌کند، سپس AppConfig می‌سازد."""
        _load_dotenv_if_present()
        return cls()


def _load_dotenv_if_present(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")
