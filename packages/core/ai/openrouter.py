"""OpenRouter chat-completions client."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import requests


@dataclass
class OpenRouterConfig:
    api_key: str
    model: str = "openai/gpt-4o-mini"
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    timeout_s: int = 60
    max_retries: int = 2
    retry_base_delay_s: float = 0.5


class OpenRouterError(Exception):
    def __init__(
        self,
        user_message: str,
        technical_detail: str = "",
        status_code: int | None = None,
    ):
        super().__init__(technical_detail or user_message)
        self.user_message = user_message
        self.technical_detail = technical_detail
        self.status_code = status_code


class OpenRouterClient:
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(
        self,
        config: OpenRouterConfig,
        session: requests.Session | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        if not config.api_key:
            raise ValueError("کلید OpenRouter تنظیم نشده است.")
        if not config.model:
            raise ValueError("مدل OpenRouter تنظیم نشده است.")
        self.config = config
        self.session = session or requests.Session()
        self.sleep_fn = sleep_fn

    def generate(
        self,
        history: list[tuple[str, str]],
        prompt: str,
        system_instruction: str = "",
    ) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        for role, content in history:
            if role == "model":
                role = "assistant"
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "X-Title": "MODASR ECOSYSTEM",
        }

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session.post(
                    self.config.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_s,
                )
            except requests.RequestException as exc:
                if attempt < self.config.max_retries:
                    self.sleep_fn(self.config.retry_base_delay_s * (2 ** attempt))
                    continue
                raise OpenRouterError(
                    "ارتباط با سرویس هوش مصنوعی برقرار نشد. کمی بعد دوباره تلاش کن.",
                    f"Network error: {type(exc).__name__}",
                ) from exc

            if response.status_code in self.RETRYABLE_STATUS:
                if attempt < self.config.max_retries:
                    self.sleep_fn(self.config.retry_base_delay_s * (2 ** attempt))
                    continue

            if response.status_code != 200:
                status = response.status_code
                try:
                    data = response.json()
                    detail = str(data.get("error", data))[:500]
                except (ValueError, AttributeError):
                    detail = "پاسخ خطای غیر JSON"
                if status in (401, 403):
                    message = "کلید OpenRouter معتبر نیست یا اجازه دسترسی ندارد."
                elif status == 402:
                    message = "اعتبار یا موجودی حساب OpenRouter کافی نیست."
                elif status == 429:
                    message = "درخواست‌ها به محدودیت سرویس رسیده‌اند؛ کمی بعد دوباره تلاش کن."
                elif status == 404:
                    message = "مدل انتخاب‌شده در OpenRouter پیدا نشد یا در دسترس نیست."
                else:
                    message = "سرویس هوش مصنوعی موقتاً خطا داد؛ بعداً دوباره تلاش کن."
                raise OpenRouterError(message, f"HTTP {status}: {detail}", status)

            try:
                data = response.json()
                choices = data.get("choices", [])
                content = choices[0]["message"]["content"]
                if isinstance(content, str) and content.strip():
                    return content.strip()
                if isinstance(content, list):
                    parts = [
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict) and item.get("type") == "text"
                    ]
                    result = "".join(parts).strip()
                    if result:
                        return result
            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                pass

            raise OpenRouterError(
                "پاسخ معتبر از هوش مصنوعی دریافت نشد.",
                "Missing or invalid choices[0].message.content",
            )

        raise OpenRouterError("درخواست ناموفق بود؛ بعداً دوباره تلاش کن.")

