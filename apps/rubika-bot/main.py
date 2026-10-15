"""اجرای مستقل ربات روبیکا با هسته مشترک AI و دیتابیس."""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "packages" / "core"

for item in (CORE, CORE / "ai", Path(__file__).resolve().parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from config import AppConfig  # noqa: E402
from database import Database  # noqa: E402
from openrouter import (  # noqa: E402
    OpenRouterClient,
    OpenRouterConfig,
    OpenRouterError,
)
from adapter import RubikaAdapter  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("rubika-bot")

SYSTEM_INSTRUCTION = (
    "شما دستیار هوش مصنوعی MODASR هستید "
    "و به فارسی، مودبانه و مختصر پاسخ می‌دهید."
)


def build_dependencies(cfg: AppConfig):
    missing = cfg.problems(["rubika_bot_token", "openrouter_api_key"])
    if missing:
        for item in missing:
            log.error("پیکربندی ناقص: %s", item)
        raise SystemExit(1)

    db = Database(cfg.db_path)
    ai = OpenRouterClient(
        OpenRouterConfig(
            api_key=cfg.openrouter_api_key,
            model=cfg.openrouter_model,
            timeout_s=cfg.openrouter_timeout_s,
            max_retries=cfg.openrouter_max_retries,
        )
    )
    adapter = RubikaAdapter(cfg.rubika_bot_token)
    return db, ai, adapter


def handle_message(db, ai, adapter, msg) -> None:
    text = (msg.text or "").strip()

    if not text:
        adapter.send_text(
            msg.chat_id,
            "فعلاً در نسخه اولیه فقط پیام متنی پشتیبانی می‌شود.",
        )
        return

    if text == "/start":
        adapter.send_text(
            msg.chat_id,
            "سلام! من دستیار هوش مصنوعی MODASR هستم. "
            "پیامت را بفرست تا کمکت کنم.",
        )
        return

    if text == "/help":
        adapter.send_text(
            msg.chat_id,
            "راهنما: سؤال یا درخواستت را به صورت پیام متنی ارسال کن.",
        )
        return

    user = db.get_or_create_user(
        adapter.platform_name,
        msg.user_id,
        msg.user_display_name,
    )
    history = db.recent_messages(user.id, limit=16)

    try:
        reply = ai.generate(
            history=history,
            prompt=text,
            system_instruction=SYSTEM_INSTRUCTION,
        )
    except OpenRouterError as exc:
        log.warning(
            "OpenRouter error for user %s: %s",
            user.id,
            exc.technical_detail,
        )
        adapter.send_text(msg.chat_id, f"❌ {exc.user_message}")
        return

    db.append_message(user.id, "user", text)
    db.append_message(user.id, "model", reply)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db.increment_usage(user.id, "chat", today)

    result = adapter.send_text(msg.chat_id, reply)
    if not result.ok:
        log.warning("ارسال پاسخ روبیکا ناموفق بود: %s", result.error)


def poll_once(db, ai, adapter, offset_id: str | None) -> str | None:
    try:
        result = adapter.get_updates(offset_id=offset_id, limit=10)
    except Exception as exc:
        log.warning("دریافت آپدیت روبیکا ناموفق بود: %s", exc)
        return offset_id

    updates = result.get("updates", [])
    if not isinstance(updates, list):
        log.warning("فیلد updates در پاسخ روبیکا معتبر نیست.")
        return offset_id

    for update in updates:
        if not isinstance(update, dict):
            continue

        try:
            msg = adapter.parse_update(update)
            if msg is not None:
                handle_message(db, ai, adapter, msg)
        except Exception:
            log.exception("خطا در پردازش یک آپدیت روبیکا")

    next_offset = result.get("next_offset_id")
    if next_offset is not None and str(next_offset):
        return str(next_offset)

    return offset_id


def run_polling(db, ai, adapter) -> None:
    offset_id = None
    log.info("شروع دریافت پیام‌های روبیکا...")

    while True:
        offset_id = poll_once(db, ai, adapter, offset_id)
        time.sleep(1)


def main() -> None:
    cfg = AppConfig.load()
    db, ai, adapter = build_dependencies(cfg)

    health = adapter.health_check()
    if not health.ok:
        log.error("اتصال به روبیکا ناموفق بود: %s", health.detail)
        raise SystemExit(1)

    log.info("اتصال به روبیکا برقرار شد: %s", health.detail)
    run_polling(db, ai, adapter)


if __name__ == "__main__":
    main()
