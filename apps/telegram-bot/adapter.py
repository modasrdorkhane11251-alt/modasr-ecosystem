"""
آداپتور تلگرام: پیاده‌سازی PlatformAdapter روی Bot API رسمی تلگرام با requests.

عمداً از python-telegram-bot استفاده نشده: این فایل باید مستقل و قابل‌تست
با unittest ساده باشد. اگر بعداً خواستید از کتابخانه‌ی کامل‌تری (polling خودکار،
webhook، و غیره) استفاده کنید، همین کلاس را پشت PlatformAdapter نگه دارید.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "core"))
from platform_adapter import HealthStatus, IncomingMessage, MediaKind, PlatformAdapter, SendResult  # noqa: E402

TELEGRAM_MEDIA_MAP = {
    "photo": MediaKind.PHOTO,
    "voice": MediaKind.VOICE,
    "audio": MediaKind.AUDIO,
    "video": MediaKind.VIDEO,
    "video_note": MediaKind.VIDEO,
    "document": MediaKind.DOCUMENT,
}


class TelegramAdapter(PlatformAdapter):
    platform_name = "telegram"

    def __init__(self, bot_token: str, session: requests.Session | None = None, timeout_s: int = 15):
        if not bot_token:
            raise ValueError("bot_token خالی است.")
        self._token = bot_token
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._session = session or requests.Session()
        self._timeout = timeout_s

    def parse_update(self, raw_update: dict) -> IncomingMessage | None:
        if "callback_query" in raw_update:
            cq = raw_update["callback_query"]
            msg = cq.get("message", {})
            chat = msg.get("chat", {})
            user = cq.get("from", {})
            return IncomingMessage(
                platform=self.platform_name,
                chat_id=str(chat.get("id", "")),
                user_id=str(user.get("id", "")),
                user_display_name=user.get("first_name", ""),
                callback_data=cq.get("data"),
                raw=raw_update,
            )

        msg = raw_update.get("message") or raw_update.get("edited_message")
        if not msg:
            return None
        chat = msg.get("chat", {})
        user = msg.get("from", {})
        media_kind = None
        file_id = None
        for key, kind in TELEGRAM_MEDIA_MAP.items():
            val = msg.get(key)
            if val:
                media_kind = kind
                file_id = val[-1]["file_id"] if isinstance(val, list) else val.get("file_id")
                break
        return IncomingMessage(
            platform=self.platform_name,
            chat_id=str(chat.get("id", "")),
            user_id=str(user.get("id", "")),
            user_display_name=user.get("first_name", ""),
            text=msg.get("text"),
            media_kind=media_kind,
            media_file_id=file_id,
            caption=msg.get("caption"),
            raw=raw_update,
        )

    def send_text(self, chat_id: str, text: str) -> SendResult:
        try:
            r = self._session.post(f"{self._base}/sendMessage",
                                   json={"chat_id": chat_id, "text": text[:4096]},
                                   timeout=self._timeout)
        except requests.RequestException as e:
            return SendResult(ok=False, error=f"network: {e}")
        data = r.json()
        if not data.get("ok"):
            return SendResult(ok=False, error=data.get("description", f"HTTP {r.status_code}"))
        return SendResult(ok=True, message_id=str(data["result"]["message_id"]))

    TELEGRAM_SEND_METHOD = {
        MediaKind.PHOTO: ("sendPhoto", "photo"),
        MediaKind.VOICE: ("sendVoice", "voice"),
        MediaKind.AUDIO: ("sendAudio", "audio"),
        MediaKind.VIDEO: ("sendVideo", "video"),
        MediaKind.DOCUMENT: ("sendDocument", "document"),
    }

    def send_media(self, chat_id: str, kind: MediaKind, file_path: str, caption: str = "") -> SendResult:
        method, field = self.TELEGRAM_SEND_METHOD.get(kind, (None, None))
        if not method:
            return SendResult(ok=False, error=f"نوع رسانه‌ی پشتیبانی‌نشده: {kind}")
        try:
            f = open(file_path, "rb")
        except OSError as e:
            return SendResult(ok=False, error=f"فایل قابل خواندن نبود: {e}")
        # requests.exceptions.ConnectionError از OSError هم ارث می‌برد؛ به همین خاطر خطای
        # شبکه باید جدا از خطای باز کردن فایل گرفته شود، وگرنه به‌اشتباه "فایل خوانده
        # نشد" گزارش می‌شود در حالی که فایل باز شده و مشکل واقعاً در اتصال شبکه است.
        try:
            with f:
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption[:1024]
                r = self._session.post(f"{self._base}/{method}", data=data,
                                       files={field: f}, timeout=max(self._timeout, 60))
        except requests.RequestException as e:
            return SendResult(ok=False, error=f"network: {e}")
        result = r.json()
        if not result.get("ok"):
            return SendResult(ok=False, error=result.get("description", f"HTTP {r.status_code}"))
        return SendResult(ok=True, message_id=str(result["result"]["message_id"]))

    def health_check(self) -> HealthStatus:
        try:
            r = self._session.get(f"{self._base}/getMe", timeout=self._timeout)
        except requests.RequestException as e:
            return HealthStatus(ok=False, detail=f"network: {e}")
        data = r.json()
        if data.get("ok"):
            return HealthStatus(ok=True, detail=f"@{data['result'].get('username', '')}")
        return HealthStatus(ok=False, detail=data.get("description", f"HTTP {r.status_code}"))
