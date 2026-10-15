#!/usr/bin/env python3
"""
رمز عبور مدیر پنل را می‌گیرد (بدون نمایش روی صفحه) و هش PBKDF2 آن را چاپ می‌کند تا
در .env به‌عنوان ADMIN_PASSWORD_HASH بگذارید. خود رمز خام هیچ‌جا چاپ یا ذخیره نمی‌شود.

اجرا:
    python3 scripts/set_admin_password.py
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "web-panel"))
from auth import hash_password  # noqa: E402


def main() -> int:
    pw1 = getpass.getpass("رمز عبور جدید مدیر پنل: ")
    if len(pw1) < 10:
        print("❌ رمز باید حداقل ۱۰ کاراکتر باشد.")
        return 1
    pw2 = getpass.getpass("تکرار رمز: ")
    if pw1 != pw2:
        print("❌ دو رمز یکسان نبودند.")
        return 1
    print("\nاین خط را در .env بگذارید (به‌جای خط قبلی ADMIN_PASSWORD_HASH، اگر بود):\n")
    print(f"ADMIN_PASSWORD_HASH={hash_password(pw1)}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
