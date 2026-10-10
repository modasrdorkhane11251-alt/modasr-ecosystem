"""
اینترفیس مشترک آداپتورهای پیام‌رسان.

منطق AI، دیتابیس و اشتراک هیچ‌وقت مستقیم با SDK یه پیام‌رسان خاص کار نمی‌کنه؛
همیشه از پشت همین اینترفیس. هر پیام‌رسان (تلگرام، بله، ...) این کلاس رو پیاده می‌کنه
و تفاوت‌های API خودش رو همین‌جا مخفی می‌کنه.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class MediaKind(str, Enum):
    PHOTO = "photo"
    VOICE = "voice"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


@dataclass
class IncomingMessage:
    """نمایش یکسان یه پیام ورودی، صرف‌نظر از پیام‌رسان."""
    platform: str
    chat_id: str
    user_id: str
    user_display_name: str
    text: str | None = None
    media_kind: MediaKind | None = None
    media_file_id: str | None = None
    caption: str | None = None
    callback_data: str | None = None
    raw: dict | None = None  # آپدیت خام، فقط برای دیباگ؛ منطق اصلی نباید بهش وابسته باشه


@dataclass
class SendResult:
    ok: bool
    message_id: str | None = None
    error: str | None = None


@dataclass
class HealthStatus:
    ok: bool
    detail: str = ""


class PlatformAdapter(ABC):
    """هر پیام‌رسان این را پیاده می‌کند. متدها قصداً کم و صریح‌اند."""

    platform_name: str

    @abstractmethod
    def parse_update(self, raw_update: dict) -> IncomingMessage | None:
        """یک آپدیت خام را به IncomingMessage تبدیل می‌کند؛ اگر قابل‌پردازش نبود None می‌دهد."""

    @abstractmethod
    def send_text(self, chat_id: str, text: str) -> SendResult:
        ...

    def send_media(self, chat_id: str, kind: MediaKind, file_path: str, caption: str = "") -> SendResult:
        """پیاده‌سازی پیش‌فرض: پشتیبانی نشده. هر آداپتور در صورت پشتیبانی override می‌کند."""
        return SendResult(ok=False, error=f"{self.platform_name} از ارسال {kind.value} در این آداپتور پشتیبانی نمی‌کند.")

    @abstractmethod
    def health_check(self) -> HealthStatus:
        ...
