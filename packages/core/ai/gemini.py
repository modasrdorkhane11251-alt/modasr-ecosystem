"""
کلاینت Gemini: یک نقطه‌ی ورود برای همه‌ی آداپتورهای پیام‌رسان.

چرا requests و نه httpx؟ در محیط توسعه‌ی فعلی دسترسی شبکه برای نصب پکیج نبود؛
requests از قبل نصب بود. وقتی روی سرور خودتان با اینترنت نصب می‌کنید، آزادید
این را به httpx (async) عوض کنید — رابط عمومی (GeminiClient.generate) همینطور می‌ماند.

مدیریت خطا:
  400 → درخواست بد (پیام/تنظیمات کاربر)، retry نمی‌شود
  401/403 → کلید نامعتبر یا بدون دسترسی، retry نمی‌شود، باید فوراً به ادمین گزارش شود
  404 → مدل یافت نشد (اسم مدل اشتباه یا دیگر در دسترس نیست)، retry نمی‌شود
  429 → محدودیت نرخ، retry با backoff
  5xx → خطای سرور گوگل، retry با backoff
  timeout/network → retry با backoff
بعد از اتمام تلاش‌ها، GeminiError با پیام فارسیِ مناسب برای کاربر نهایی raise می‌شود؛
جزئیات فنی (status code خام و غیره) فقط در GeminiError.technical_detail است و
آداپتورها نباید آن را مستقیم به کاربر عادی نشان دهند.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS = {400, 401, 403, 404}


class GeminiError(Exception):
    def __init__(self, user_message: str, technical_detail: str = "", status_code: int | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.technical_detail = technical_detail
        self.status_code = status_code


@dataclass
class GeminiConfig:
    api_key: str
    model: str = "gemini-2.5-flash"
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"
    timeout_s: int = 30
    max_retries: int = 2
    retry_base_delay_s: float = 0.5


def _status_to_user_message(status: int) -> str:
    return {
        400: "درخواست نامعتبر بود. لطفاً پیام را بازنویسی کنید.",
        401: "کلید API معتبر نیست. (ادمین باید GEMINI_API_KEY را بررسی کند)",
        403: "دسترسی به این مدل مجاز نیست. (ادمین باید دسترسی کلید API را بررسی کند)",
        404: "مدل هوش مصنوعی یافت نشد. (ادمین باید نام مدل را بررسی کند)",
        429: "سرویس هوش مصنوعی شلوغ است. چند لحظه دیگر دوباره امتحان کنید.",
        500: "خطای موقت سرویس هوش مصنوعی. دوباره امتحان کنید.",
        502: "خطای موقت سرویس هوش مصنوعی. دوباره امتحان کنید.",
        503: "سرویس هوش مصنوعی موقتاً در دسترس نیست. دوباره امتحان کنید.",
        504: "پاسخ سرویس هوش مصنوعی طول کشید. دوباره امتحان کنید.",
    }.get(status, f"خطای سرویس هوش مصنوعی (کد {status}).")


class GeminiClient:
    def __init__(self, config: GeminiConfig, session: requests.Session | None = None,
                 sleep_fn=time.sleep):
        if not config.api_key:
            raise ValueError("GeminiConfig.api_key خالی است؛ GeminiClient نباید بدون کلید ساخته شود.")
        self.config = config
        self.session = session or requests.Session()
        self._sleep = sleep_fn

    def generate(self, history: list[tuple[str, str]], prompt: str,
                 system_instruction: str = "") -> str:
        """history: لیست (role, text) با role در {'user','model'}. آخرین پیام کاربر در prompt است."""
        contents = [{"role": role, "parts": [{"text": text}]} for role, text in history]
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        payload: dict = {"contents": contents, "generationConfig": {"temperature": 0.7}}
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{self.config.base_url}/{self.config.model}:generateContent"
        headers = {"Content-Type": "application/json", "X-goog-api-key": self.config.api_key}

        last_error: GeminiError | None = None
        attempts = self.config.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                resp = self.session.post(url, json=payload, headers=headers, timeout=self.config.timeout_s)
            except requests.Timeout:
                last_error = GeminiError("سرویس هوش مصنوعی پاسخ نداد (timeout).", "timeout")
                self._maybe_wait(attempt, attempts)
                continue
            except requests.RequestException as e:
                last_error = GeminiError("اتصال به سرویس هوش مصنوعی برقرار نشد.", f"network: {e}")
                self._maybe_wait(attempt, attempts)
                continue

            if resp.status_code == 200:
                return self._extract_text(resp.json())

            detail = resp.text[:500]
            status = resp.status_code
            last_error = GeminiError(_status_to_user_message(status), detail, status)
            if status in NON_RETRYABLE_STATUS:
                raise last_error
            if status in RETRYABLE_STATUS:
                self._maybe_wait(attempt, attempts)
                continue
            # کد ناشناخته: محتاطانه retry نمی‌کنیم
            raise last_error

        raise last_error  # تمام تلاش‌ها تمام شد

    def _maybe_wait(self, attempt: int, attempts: int) -> None:
        if attempt < attempts:
            self._sleep(self.config.retry_base_delay_s * (2 ** (attempt - 1)))

    @staticmethod
    def _extract_text(data: dict) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "نامشخص")
            raise GeminiError(f"پاسخ مسدود شد ({reason}).", str(data)[:500])
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise GeminiError("مدل پاسخ متنی برنگرداند.", str(data)[:500])
        return text
