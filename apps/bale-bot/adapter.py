"""
آداپتور بله.

بله یک Bot API رسمی و مستند دارد (https://dev.bale.ai) که عمداً شبیه به Telegram
Bot API طراحی شده (همان متدهای getMe/sendMessage/getUpdates با همان شکل JSON).
این را هم در مستندات رسمی بله و هم در نمونه‌کد `srckde_6a53c11490a18/include/bale.php`
که در همین پروژه بررسی شد (استفاده از tapi.bale.ai) دیدیم.

⚠️ آنچه تایید نشده: پوشش کامل متدها و رفتار تک‌تک پارامترها، چون اینجا دسترسی
اینترنت برای چک کردن لحظه‌ای مستندات یا زدن یک درخواست واقعی نبود. قبل از استفاده‌ی
جدی، `health_check()` را با یک توکن واقعی اجرا کنید و اگر پاسخ انتظار را برآورده
نکرد، این فایل را با مستندات فعلی dev.bale.ai مطابقت دهید.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "core"))
from platform_adapter import HealthStatus, IncomingMessage, MediaKind, PlatformAdapter, SendResult  # noqa: E402

BALE_MEDIA_MAP = {
    "photo": MediaKind.PHOTO,
    "voice": MediaKind.VOICE,
    "audio": MediaKind.AUDIO,
    "video": MediaKind.VIDEO,
    "document": MediaKind.DOCUMENT,
}


class BaleAdapter(PlatformAdapter):
    platform_name = "bale"

    def __init__(self, bot_token: str, session: requests.Session | None = None, timeout_s: int = 15):
        if not bot_token:
            raise ValueError("bot_token خالی است.")
        self._base = f"https://tapi.bale.ai/bot{bot_token}"
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
        msg = raw_update.get("message")
        if not msg:
            return None
        chat = msg.get("chat", {})
        user = msg.get("from", {})
        media_kind, file_id = None, None
        for key, kind in BALE_MEDIA_MAP.items():
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

    def health_check(self) -> HealthStatus:
        try:
            r = self._session.get(f"{self._base}/getMe", timeout=self._timeout)
        except requests.RequestException as e:
            return HealthStatus(ok=False, detail=f"network: {e}")
        data = r.json()
        if data.get("ok"):
            return HealthStatus(ok=True, detail=f"@{data['result'].get('username', '')}")
        return HealthStatus(ok=False, detail=data.get("description", f"HTTP {r.status_code}"))
