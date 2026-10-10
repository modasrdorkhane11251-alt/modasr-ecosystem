"""
آداپتور روبیکا — عمداً ناقص.

روبیکا هیچ Bot API رسمی و عمومی ندارد. آنچه در نمونه‌های رایج (ازجمله فایلی که
در همین پروژه بررسی شد: rubika_downloader.py) دیده می‌شود، یک API داخلیِ وب/اپ
روبیکاست که:
  1. مستند رسمی ندارد و بدون اطلاع قبلی می‌تواند تغییر کند یا قطع شود.
  2. با لاگینِ شماره‌تلفن + کد پیامکیِ یک حساب کاربری واقعی کار می‌کند — نه یک
     "حساب ربات" جدا مثل تلگرام/بله. یعنی این کد باید به اکانت شخصی/تستی شما وصل شود.
  3. استفاده‌ی خودکار از آن ممکن است طبق قوانین استفاده‌ی روبیکا نقض محسوب شود و
     به مسدودشدن همان اکانت منجر شود.

به همین دلیل این آداپتور را کامل پیاده‌سازی نکردم — نه چون سخت است، بلکه چون این
یک تصمیم است که فقط خود شما باید بگیرید (قبول کردن ریسک اکانت شخصی).

اگر تصمیم گرفتید ادامه بدهید، این کلاس را با همان اینترفیس PlatformAdapter کامل
می‌کنم، دقیقاً مثل TelegramAdapter/BaleAdapter.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "core"))
from platform_adapter import HealthStatus, IncomingMessage, PlatformAdapter, SendResult  # noqa: E402


class RubikaAdapter(PlatformAdapter):
    platform_name = "rubika"

    def __init__(self, *_args, **_kwargs):
        raise NotImplementedError(
            "آداپتور روبیکا عمداً پیاده‌سازی نشده؛ دلیلش را در بالای همین فایل و در "
            "docs/NEXT_STEPS.md بخوانید. قبل از ادامه، باید صریحاً بپذیرید از یک API "
            "غیررسمی با اکانت کاربری واقعی استفاده می‌کنید."
        )

    def parse_update(self, raw_update: dict) -> IncomingMessage | None:  # pragma: no cover
        raise NotImplementedError

    def send_text(self, chat_id: str, text: str) -> SendResult:  # pragma: no cover
        raise NotImplementedError

    def health_check(self) -> HealthStatus:  # pragma: no cover
        raise NotImplementedError
