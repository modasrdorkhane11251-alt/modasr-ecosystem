"""
حلقه‌ی اجرای واقعی بله: ساختارش عمداً دوقلوی `apps/telegram-bot/main.py` است،
چون هر دو پشت همان `PlatformAdapter` کار می‌کنند؛ تنها تفاوت، آداپتور و نام متغیر محیطی توکن است.

اجرا: از ریشه‌ی modasr-ecosystem،  `python apps/bale-bot/main.py`
نیاز به .env با BALE_BOT_TOKEN و OPENROUTER_API_KEY.

⚠️ این فایل در محیط توسعه فقط با Mock تست شده (بدون اینترنت). جزئیات در docs/TEST_REPORT.md.
این حلقه کاملاً مستقل از تلگرام است: نه import می‌کند و نه state به اشتراک می‌گذارد؛
فقط همان `Database` و `OpenRouterClient` مشترک هسته را دوباره می‌سازد (دو پردازه‌ی جدا).
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "packages" / "core"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(CORE / "ai"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import AppConfig  # noqa: E402
from database import SUBSCRIPTION_PLANS, Database  # noqa: E402
from openrouter import OpenRouterClient, OpenRouterConfig, OpenRouterError  # noqa: E402
from adapter import BaleAdapter  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bale-bot")

SYSTEM_INSTRUCTION = "شما دستیار هوش مصنوعی MODASR هستید و به فارسی، مودبانه و مختصر پاسخ می‌دهید."


def build_dependencies(cfg: AppConfig):
    missing = cfg.problems(["bale_bot_token", "openrouter_api_key"])
    if missing:
        for m in missing:
            log.error("پیکربندی ناقص: %s", m)
        raise SystemExit(1)
    db = Database(cfg.db_path)
    ai = OpenRouterClient(OpenRouterConfig(
        api_key=cfg.openrouter_api_key,
        model=cfg.openrouter_model,
        timeout_s=cfg.openrouter_timeout_s,
        max_retries=cfg.openrouter_max_retries,
    ))
    adapter = BaleAdapter(cfg.bale_bot_token)
    return db, ai, adapter


def check_quota(db: Database, user_id: int) -> tuple[bool, str | None]:
    """همان منطق apps/telegram-bot/main.py:check_quota؛ عمداً اینجا هم کپی شده (نه
    import از ماژول تلگرام) چون apps/telegram-bot نباید وابستگی تولیدی از apps/bale-bot
    بگیرد یا برعکس — این دو پردازه‌ی کاملاً مستقل‌اند."""
    sub = db.get_subscription(user_id)
    plan_key = sub.plan if (sub and sub.is_active_now()) else "free"
    plan = SUBSCRIPTION_PLANS.get(plan_key)
    if plan is None:
        log.error("پلن ناشناخته در دیتابیس: %s برای کاربر %s؛ به‌صورت محافظه‌کارانه رد می‌شود.", plan_key, user_id)
        return False, "⚠️ خطای پیکربندی پلن اشتراک شما. به ادمین اطلاع دهید."
    limit = plan["daily_chat_limit"]
    if limit is None:
        return True, None
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = db.get_usage(user_id, "chat", today)
    if used >= limit:
        return False, (f"⚠️ سقف {limit} پیام رایگان امروز شما تمام شد. برای ادامه، اشتراک تهیه کنید "
                       "یا فردا دوباره امتحان کنید.")
    return True, None


def handle_message(db: Database, ai: OpenRouterClient, adapter: BaleAdapter, msg) -> None:
    if not msg.text:
        adapter.send_text(msg.chat_id, "فعلاً فقط پیام متنی پشتیبانی می‌شود (نسخه‌ی اولیه‌ی هسته).")
        return
    user = db.get_or_create_user(adapter.platform_name, msg.user_id, msg.user_display_name)
    allowed, deny_message = check_quota(db, user.id)
    if not allowed:
        adapter.send_text(msg.chat_id, deny_message)
        return
    history = db.recent_messages(user.id, limit=16)
    try:
        reply = ai.generate(history=history, prompt=msg.text, system_instruction=SYSTEM_INSTRUCTION)
    except OpenRouterError as e:
        log.warning("خطای OpenRouter برای کاربر %s: %s", user.id, e.technical_detail)
        adapter.send_text(msg.chat_id, f"❌ {e.user_message}")
        return
    db.append_message(user.id, "user", msg.text)
    db.append_message(user.id, "model", reply)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db.increment_usage(user.id, "chat", today)
    adapter.send_text(msg.chat_id, reply)


def poll_once(db: Database, ai: OpenRouterClient, adapter: BaleAdapter, offset: int | None) -> int | None:
    """یک دور getUpdates + پردازش روی بله. هرگز استثنا بیرون نمی‌دهد (مثل نسخه‌ی تلگرام).

    ⚠️ فرض بر این است که getUpdates بله دقیقاً همان شکل پاسخ تلگرام را دارد
    (طبق مستندات رسمی بله). این فرض با تست زنده تایید نشده؛ اگر در تست زنده
    فرق داشت، همین تابع باید اصلاح شود.
    """
    import requests
    try:
        params = {"timeout": 20}
        if offset is not None:
            params["offset"] = offset
        r = requests.get(f"{adapter._base}/getUpdates", params=params, timeout=25)
    except requests.RequestException as e:
        log.warning("خطای شبکه در getUpdates (بله): %s", e)
        return offset

    if r.status_code != 200:
        log.warning("getUpdates بله وضعیت HTTP غیرمنتظره برگرداند: %s", r.status_code)
        return offset

    try:
        data = r.json()
    except ValueError:
        log.warning("getUpdates بله پاسخ JSON نامعتبر برگرداند (بدنه: %s کاراکتر)", len(r.text or ""))
        return offset

    if not isinstance(data, dict) or not data.get("ok"):
        log.warning("getUpdates بله پاسخ ok=false داد: %s", (data or {}).get("description", "بدون توضیح"))
        return offset

    results = data.get("result")
    if not isinstance(results, list):
        log.warning("getUpdates بله فیلد result نامعتبر/غایب برگرداند.")
        return offset

    for update in results:
        update_id = update.get("update_id")
        if update_id is None:
            log.warning("آپدیت بله بدون update_id نادیده گرفته شد.")
            continue
        offset = update_id + 1
        try:
            msg = adapter.parse_update(update)
        except Exception:  # noqa: BLE001
            log.exception("خطا در پارس آپدیت بله؛ آپدیت رد شد.")
            continue
        if msg:
            try:
                handle_message(db, ai, adapter, msg)
            except Exception:  # noqa: BLE001
                log.exception("خطای پیش‌بینی‌نشده در پردازش پیام بله")
    return offset


def run_polling(db: Database, ai: OpenRouterClient, adapter: BaleAdapter, poll_interval_s: float = 1.0) -> None:
    offset = None
    log.info("شروع polling بله...")
    while True:
        offset = poll_once(db, ai, adapter, offset)
        time.sleep(poll_interval_s)


def main() -> None:
    cfg = AppConfig.load()
    db, ai, adapter = build_dependencies(cfg)
    health = adapter.health_check()
    if not health.ok:
        log.error("اتصال به بله برقرار نشد: %s", health.detail)
        raise SystemExit(1)
    log.info("متصل به بله: %s", health.detail)
    run_polling(db, ai, adapter)


if __name__ == "__main__":
    main()
