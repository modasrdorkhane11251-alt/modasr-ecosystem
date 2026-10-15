"""
Rubika Bot API adapter.

این فایل فقط مسئول ارتباط با API روبیکا و تبدیل پیام‌ها به
ساختار مشترک PlatformAdapter است. منطق AI به روبیکا وابسته نیست.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import requests

CORE = Path(__file__).resolve().parents[2] / "packages" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from platform_adapter import (  # noqa: E402
    HealthStatus,
    IncomingMessage,
    PlatformAdapter,
    SendResult,
)


class RubikaAdapter(PlatformAdapter):
    platform_name = "rubika"

    def __init__(
        self,
        bot_token: str,
        session: requests.Session | None = None,
        timeout_s: int = 20,
    ):
        if not bot_token or not bot_token.strip():
            raise ValueError("RUBIKA_BOT_TOKEN خالی است.")

        self._token = bot_token.strip()
        self._base = f"https://botapi.rubika.ir/v3/{self._token}"
        self._session = session or requests.Session()
        self._timeout = timeout_s

    def _request(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """درخواست به Bot API و یکسان‌سازی پاسخ‌های معتبر."""
        response = self._session.post(
            f"{self._base}/{method}",
            json=payload or {},
            timeout=self._timeout,
        )
        response.raise_for_status()

        try:
            body = response.json()
        except ValueError as exc:
            raise ValueError(
                f"پاسخ متد {method}، JSON معتبر نیست."
            ) from exc

        if not isinstance(body, dict):
            raise ValueError(f"پاسخ متد {method} باید یک شیء JSON باشد.")

        # قالب رایج روبیکا: {"status": "OK", "data": {...}}
        # قالب ok/result نیز برای سازگاری احتمالی پذیرفته می‌شود.
        status = body.get("status")
        if status is not None and str(status).upper() not in {
            "OK", "SUCCESS"
        }:
            raise RuntimeError(
                str(body.get("message") or body.get("error")
                    or f"Rubika API status={status}")
            )

        if body.get("ok") is False:
            raise RuntimeError(
                str(body.get("description") or "Rubika API returned ok=false")
            )

        data = body.get("data")
        if isinstance(data, dict):
            return data

        return body

    @staticmethod
    def _first(mapping: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = mapping.get(key)
            if value is not None and value != "":
                return value
        return None

    def parse_update(
        self,
        raw_update: dict[str, Any],
    ) -> IncomingMessage | None:
        if not isinstance(raw_update, dict):
            return None

        # رویدادهای پیام و کلیک دکمه در API روبیکا ممکن است
        # ساختارهای متفاوتی داشته باشند.
        message = raw_update.get("new_message")
        inline = raw_update.get("inline_message")

        if isinstance(inline, dict):
            aux = inline.get("aux_data")
            if not isinstance(aux, dict):
                aux = {}

            chat_id = self._first(
                inline, "chat_id", "object_guid"
            ) or self._first(raw_update, "chat_id")

            if not chat_id:
                return None

            return IncomingMessage(
                platform=self.platform_name,
                chat_id=str(chat_id),
                user_id=str(
                    self._first(inline, "sender_id", "user_id")
                    or chat_id
                ),
                user_display_name=str(
                    self._first(inline, "sender_name", "first_name") or ""
                ),
                text=inline.get("text"),
                callback_data=(
                    self._first(aux, "button_id")
                    or self._first(inline, "button_id")
                ),
                raw=raw_update,
            )

        if not isinstance(message, dict):
            # بعضی رویدادها پیام قابل پردازش ندارند.
            return None

        # پیام‌های ارسالی خود ربات نباید دوباره پردازش شوند.
        sender_type = str(message.get("sender_type", "")).lower()
        if sender_type == "bot":
            return None

        chat_id = self._first(
            raw_update, "chat_id", "object_guid"
        ) or self._first(message, "chat_id", "object_guid")

        if not chat_id:
            return None

        sender = message.get("sender")
        if not isinstance(sender, dict):
            sender = {}

        user_id = (
            self._first(message, "sender_id", "user_id")
            or self._first(sender, "user_id", "id")
            or chat_id
        )

        display_name = (
            self._first(message, "sender_name", "first_name", "name")
            or self._first(sender, "first_name", "name")
            or ""
        )

        text = message.get("text")
        if text is not None:
            text = str(text)

        return IncomingMessage(
            platform=self.platform_name,
            chat_id=str(chat_id),
            user_id=str(user_id),
            user_display_name=str(display_name),
            text=text,
            caption=message.get("caption"),
            raw=raw_update,
        )

    def send_text(self, chat_id: str, text: str) -> SendResult:
        try:
            data = self._request(
                "sendMessage",
                {
                    "chat_id": str(chat_id),
                    "text": str(text),
                },
            )
        except requests.RequestException as exc:
            return SendResult(ok=False, error=f"network: {exc}")
        except (ValueError, RuntimeError) as exc:
            return SendResult(ok=False, error=str(exc))

        result = data.get("message")
        if not isinstance(result, dict):
            result = data.get("result")
        if not isinstance(result, dict):
            result = data

        message_id = self._first(
            result, "message_id", "messageId", "id"
        )

        return SendResult(
            ok=True,
            message_id=str(message_id) if message_id is not None else None,
        )

    def get_updates(
        self,
        offset_id: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"limit": limit}
        if offset_id:
            payload["offset_id"] = str(offset_id)

        return self._request("getUpdates", payload)

    def health_check(self) -> HealthStatus:
        try:
            data = self._request("getMe")
        except requests.RequestException as exc:
            return HealthStatus(ok=False, detail=f"network: {exc}")
        except (ValueError, RuntimeError) as exc:
            return HealthStatus(ok=False, detail=str(exc))

        bot = data.get("bot")
        if not isinstance(bot, dict):
            bot = data.get("result")
        if not isinstance(bot, dict):
            bot = data

        name = (
            self._first(bot, "username", "name", "first_name")
            or "Rubika bot"
        )
        return HealthStatus(ok=True, detail=str(name))
