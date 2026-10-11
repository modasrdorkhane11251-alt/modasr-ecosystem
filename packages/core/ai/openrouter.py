"""
کلاینت OpenRouter — ارائه‌دهنده‌ی اصلی هوش مصنوعی پروژه.

عمداً از همان الگوی `gemini.py` پیروی می‌کند (همان نام متد `generate(history, prompt,
system_instruction)`، همان شکل خطا) تا تغییرات لازم در `apps/telegram-bot/main.py` و
`apps/bale-bot/main.py` حداقلی باشد: فقط import و ساخت کلاینت عوض می‌شود، نه منطق پیام‌رسان.

چرا requests و نه httpx: مثل gemini.py، چون در محیط توسعه‌ی فعلی نصب پکیج جدید با
اینترنت ممکن نیست؛ requests از قبل نصب بود.

API رسمی OpenRouter: POST https://openrouter.ai/api/v1/chat/completions
فرمت درخواست/پاسخ سازگار با OpenAI Chat Completions است (model, messages[], ...).
مستندسازی خطا بر اساس همان کدهای HTTP استاندارد (docs: openrouter.ai/docs) — در این
محیط بدون اینترنت امکان چک لحظه‌ای مستندات نبود؛ قبل از اتکای جدی، با یک تست زنده
(`scripts/test_openrouter_live.py`) تایید کنید.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS = {400, 401, 403, 404}


class OpenRouterError(Exception):
    def __init__(self, user_message: str, technical_detail: str = "", status_code: int | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.technical_detail = technical_detail
        self.status_code = status_code


@dataclass
class OpenRouterConfig:
    api_key: str
    model: str = "openai/gpt-4o-mini"
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    timeout_s: int = 30
    max_retries: int = 2
    retry_base_delay_s: float = 0.5
    # این دو هدر اختیاری‌اند طبق مستندات OpenRouter (برای نمایش پروژه در رتبه‌بندی‌شان)؛
    # نبودشان خطا ایجاد نمی‌کند، فقط برای شناسایی پروژه مفیدند.
    http_referer: str = ""
    app_title: str = "MODASR ECOSYSTEM"


def _status_to_user_message(status: int) -> str:
    return {
        400: "درخواست نامعتبر بود. لطفاً پیام را بازنویسی کنید.",
        401: "کلید API معتبر نیست. (ادمین باید OPENROUTER_API_KEY را بررسی کند)",
        403: "دسترسی به این مدل مجاز نیست. (ادمین باید دسترسی کلید API یا اعتبار حساب را بررسی کند)",
        404: "مدل هوش مصنوعی یافت نشد. (ادمین باید نام مدل OPENROUTER_MODEL را بررسی کند)",
        429: "سرویس هوش مصنوعی شلوغ است یا سقف مصرف پر شده. چند لحظه دیگر دوباره امتحان کنید.",
        500: "خطای موقت سرویس هوش مصنوعی. دوباره امتحان کنید.",
        502: "خطای موقت سرویس هوش مصنوعی. دوباره امتحان کنید.",
        503: "سرویس هوش مصنوعی موقتاً در دسترس نیست. دوباره امتحان کنید.",
        504: "پاسخ سرویس هوش مصنوعی طول کشید. دوباره امتحان کنید.",
    }.get(status, f"خطای سرویس هوش مصنوعی (کد {status}).")


class OpenRouterClient:
    """اینترفیس عمومی عمداً با GeminiClient یکسان است: generate(history, prompt, system_instruction)."""

    def __init__(self, config: OpenRouterConfig, session: requests.Session | None = None,
                 sleep_fn=time.sleep):
        if not config.api_key:
            raise ValueError("OpenRouterConfig.api_key خالی است؛ OpenRouterClient نباید بدون کلید ساخته شود.")
        self.config = config
        self.session = session or requests.Session()
        self._sleep = sleep_fn

    def generate(self, history: list[tuple[str, str]], prompt: str,
                 system_instruction: str = "") -> str:
        """history: لیست (role, text) با role در {'user','model'}؛ 'model' به 'assistant' تبدیل می‌شود
        چون فرمت OpenAI/OpenRouter از 'assistant' استفاده می‌کند، نه 'model' (تفاوت با Gemini)."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        for role, text in history:
            messages.append({"role": "assistant" if role == "model" else "user", "content": text})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.config.model, "messages": messages, "temperature": 0.7}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"}
        if self.config.http_referer:
            headers["HTTP-Referer"] = self.config.http_referer
        if self.config.app_title:
            headers["X-Title"] = self.config.app_title

        last_error: OpenRouterError | None = None
        attempts = self.config.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                resp = self.session.post(self.config.base_url, json=payload, headers=headers,
                                         timeout=self.config.timeout_s)
            except requests.Timeout:
                last_error = OpenRouterError("سرویس هوش مصنوعی پاسخ نداد (timeout).", "timeout")
                self._maybe_wait(attempt, attempts)
                continue
            except requests.RequestException as e:
                last_error = OpenRouterError("اتصال به سرویس هوش مصنوعی برقرار نشد.", f"network: {e}")
                self._maybe_wait(attempt, attempts)
                continue

            if resp.status_code == 200:
                return self._extract_text(resp)

            detail = resp.text[:500]
            status = resp.status_code
            last_error = OpenRouterError(_status_to_user_message(status), detail, status)
            if status in NON_RETRYABLE_STATUS:
                raise last_error
            if status in RETRYABLE_STATUS:
                self._maybe_wait(attempt, attempts)
                continue
            raise last_error  # کد ناشناخته: محتاطانه retry نمی‌کنیم

        raise last_error

    def _maybe_wait(self, attempt: int, attempts: int) -> None:
        if attempt < attempts:
            self._sleep(self.config.retry_base_delay_s * (2 ** (attempt - 1)))

    @staticmethod
    def _extract_text(resp: requests.Response) -> str:
        try:
            data = resp.json()
        except ValueError:
            raise OpenRouterError("پاسخ سرویس هوش مصنوعی قابل‌خواندن نبود.", resp.text[:500])
        choices = data.get("choices") or []
        if not choices:
            err = (data.get("error") or {}).get("message", "پاسخ خالی")
            raise OpenRouterError(f"مدل پاسخی برنگرداند ({err}).", str(data)[:500])
        message = choices[0].get("message") or {}
        text = message.get("content")
        if not text:
            raise OpenRouterError("مدل پاسخ متنی برنگرداند.", str(data)[:500])
        return text
