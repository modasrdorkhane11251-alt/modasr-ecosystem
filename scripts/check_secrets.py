#!/usr/bin/env python3
"""
اسکن ساده‌ی پیش از انتشار: فایل‌هایی که git قرار است track/commit کند را برای الگوهای
شبیه به کلید/توکن واقعی می‌گردد. کامل و ضدگلوله نیست (هیچ اسکنری نیست)، ولی خطاهای
رایج (کپی‌پیست توکن تلگرام یا کلید API داخل کد یا مستندات) را می‌گیرد.

اجرا:
    python3 scripts/check_secrets.py          # فایل‌های tracked شده‌ی git را می‌گردد
    python3 scripts/check_secrets.py --all     # همه‌ی فایل‌های پروژه را می‌گردد (کندتر)

کد خروج: 0 = چیزی پیدا نشد، 1 = حداقل یک مورد مشکوک پیدا شد (جزئیات چاپ می‌شود،
ولی خودِ مقدار کامل secret هیچ‌وقت چاپ نمی‌شود — فقط نام فایل، خط، و نوع الگو).
این اسکریپت در .github/workflows/tests.yml هم اجرا می‌شود تا جلوی commit تصادفی
کلید واقعی را بگیرد.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Telegram/Bale bot token", re.compile(r"\b\d{6,10}:[A-Za-z0-9_-]{30,}\b")),
    ("OpenRouter-style key (sk-or-...)", re.compile(r"\bsk-or-v1-[A-Za-z0-9]{32,}\b")),
    ("Generic OpenAI-style key (sk-...)", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("Google API key (AIza...)", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Long hex string possibly a secret (40+ chars)", re.compile(r"\b[0-9a-f]{40,}\b")),
]

# فایل‌ها/پسوندهایی که عمداً نادیده گرفته می‌شوند (دیتابیس باینری، قفل‌فایل‌ها، خودِ این اسکریپت)
SKIP_SUFFIXES = {".db", ".lock", ".png", ".jpg", ".jpeg", ".gif", ".ico"}
SKIP_FILES = {"scripts/check_secrets.py"}  # الگوهای خودِ این فایل را به‌اشتباه گزارش ندهد


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
        return [ROOT / line for line in out.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def all_project_files() -> list[Path]:
    ignore_dirs = {".git", "venv", "__pycache__", "data", "backups", "node_modules"}
    out = []
    for p in ROOT.rglob("*"):
        if p.is_file() and not any(part in ignore_dirs for part in p.parts):
            out.append(p)
    return out


def scan() -> int:
    use_all = "--all" in sys.argv
    files = all_project_files() if use_all else tracked_files()
    if not files:
        print("⚠️  هیچ فایلی برای اسکن پیدا نشد (مخزن git نیست؟ از --all استفاده کنید).")
        return 0

    findings = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix in SKIP_SUFFIXES or rel in SKIP_FILES:
            continue
        if rel in (".env", ".env.bak") or rel.startswith(".env."):
            continue  # این فایل‌ها عمداً هیچ‌وقت نباید tracked باشند؛ جدا بررسی می‌شوند
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "FAKE" in line.upper() or "EXAMPLE" in line.upper() or "TEST_" in line.upper():
                continue  # نمونه‌های آموزشی/تستی را رد کن
            for name, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append((rel, line_no, name))

    if findings:
        print("❌ موارد مشکوک پیدا شد (مقدار واقعی چاپ نمی‌شود):")
        for rel, line_no, name in findings:
            print(f"   {rel}:{line_no} — الگوی «{name}»")
        print("\nاگر واقعی است: فوراً rotate کنید و از تاریخچه‌ی git هم حذفش کنید (کافی نیست فقط ویرایش کنید).")
        print("اگر نمونه/تستی بی‌خطر است: در خط حاوی‌اش کلمه‌ی FAKE یا EXAMPLE بگذارید تا نادیده گرفته شود.")
        return 1

    print(f"✅ چیزی مشکوک در {len(files)} فایل پیدا نشد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(scan())
