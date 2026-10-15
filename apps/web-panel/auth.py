"""
احراز هویت مدیر: هش رمز با PBKDF2 (فقط کتابخانه‌ی استاندارد پایتون، بدون bcrypt/passlib
چون در محیط توسعه امکان نصب پکیج جدید نبود) + نشست‌های سمت سرور (نه JWT، برای سادگی
و امکان ابطال فوری).

رمز عبور هیچ‌وقت خام ذخیره نمی‌شود. فرمت ذخیره در .env (کلید ADMIN_PASSWORD_HASH):
    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
این هش را با `scripts/set_admin_password.py` بسازید؛ رمز خام هیچ‌جا لاگ نمی‌شود.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

PBKDF2_ITERATIONS = 260_000
SESSION_TTL_SECONDS = 8 * 3600  # ۸ ساعت


def hash_password(plain_password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        algo, iterations_s, salt, hash_hex = stored_hash.split("$")
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_s)
    except (ValueError, AttributeError):
        return False
    computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return hmac.compare_digest(computed.hex(), hash_hex)


class SessionStore:
    """نشست‌ها فقط در حافظه‌ی پردازه نگه داشته می‌شوند. با ری‌استارت سرور، همه خارج می‌شوند
    (قابل‌قبول برای یک پنل تک‌ادمین؛ برای چند ادمین/چند پردازه باید به دیتابیس منتقل شود)."""

    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS):
        self._sessions: dict[str, float] = {}
        self._ttl = ttl_seconds

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = time.time() + self._ttl
        return token

    def is_valid(self, token: str | None) -> bool:
        if not token:
            return False
        expiry = self._sessions.get(token)
        if expiry is None:
            return False
        if time.time() > expiry:
            del self._sessions[token]
            return False
        return True

    def destroy(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)

    def purge_expired(self) -> None:
        now = time.time()
        for token in [t for t, exp in self._sessions.items() if exp < now]:
            del self._sessions[token]


def get_admin_password_hash() -> str:
    return os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
