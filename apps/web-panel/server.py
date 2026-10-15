"""
سرور پنل مدیریت MODASR — فقط با کتابخانه‌ی استاندارد پایتون (بدون Flask/FastAPI)،
چون در محیط توسعه‌ی این پروژه نصب پکیج جدید با pip ممکن نیست. اگر روی سرور خودتان
اینترنت دارید و ترجیح می‌دهید از Flask استفاده کنید، این فایل را می‌توانید جایگزین
کنید؛ اینترفیس API (مسیرها و JSON) همین مستندسازی پایین صفحه است.

هر پاسخ این سرور از داده‌ی واقعی (دیتابیس، health check واقعی، یا OpenRouter واقعی)
می‌آید — هیچ عدد یا وضعیت نمایشی/ساختگی اینجا نیست. اگر چیزی قابل‌اندازه‌گیری نباشد
(مثلاً هنوز تست زنده نشده)، API همین را صریح در پاسخ می‌گذارد (`"checked": false`).

اجرا:
    cd modasr-ecosystem
    python3 apps/web-panel/server.py            # پیش‌فرض: 127.0.0.1:8080
    PANEL_HOST=0.0.0.0 PANEL_PORT=8080 python3 apps/web-panel/server.py
در تولید، این سرور را پشت یک reverse proxy با HTTPS واقعی (nginx/Caddy) بگذارید؛
خودش TLS ندارد. به 127.0.0.1 محدودش کنید مگر proxy جلویش باشد.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "packages" / "core"
for p in (CORE, CORE / "ai", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from config import AppConfig  # noqa: E402
from database import SUBSCRIPTION_PLANS, Database  # noqa: E402
from openrouter import OpenRouterClient, OpenRouterConfig, OpenRouterError  # noqa: E402
from auth import SessionStore, get_admin_password_hash, verify_password  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s panel %(message)s")
log = logging.getLogger("web-panel")

STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_COOKIE = "modasr_session"


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "•" * len(value)
    return f"{value[:3]}{'•' * (len(value) - 5)}{value[-2:]}"


class PanelState:
    """یک نمونه از این کلاس ساخته می‌شود و بین همه‌ی درخواست‌ها به اشتراک می‌رود.
    هر متد get_* داده را تازه از دیتابیس/شبکه می‌خواند؛ چیزی کش دائمی نمی‌شود
    (به‌جز نتیجه‌ی آخرین health check، که زمانش هم نشان داده می‌شود)."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.db = Database(cfg.db_path)
        self.sessions = SessionStore()
        self._health_cache: dict[str, dict] = {}
        self._health_lock = threading.Lock()

    # ---- داشبورد: آمار واقعی از دیتابیس ----------------------------
    def dashboard_stats(self) -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = self.db._conn.execute(
            "SELECT platform, COUNT(*) AS n FROM users GROUP BY platform"
        ).fetchall()
        users_by_platform = {r["platform"]: r["n"] for r in rows}
        total_users = sum(users_by_platform.values())

        usage_today = self.db._conn.execute(
            "SELECT feature, COUNT(DISTINCT user_id) AS users, SUM(count) AS total "
            "FROM usage_records WHERE day = ? GROUP BY feature", (today,)
        ).fetchall()
        usage = [{"feature": r["feature"], "distinct_users": r["users"], "total_calls": r["total"]}
                for r in usage_today]

        total_messages = self.db._conn.execute(
            "SELECT COUNT(*) AS n FROM conversations"
        ).fetchone()["n"]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_users": total_users,
            "users_by_platform": users_by_platform,
            "usage_today": usage,
            "total_conversation_messages": total_messages,
        }

    # ---- کاربران -------------------------------------------------
    def list_users(self, platform: str | None, limit: int) -> list[dict]:
        q = "SELECT id, platform, platform_user_id, display_name, created_at FROM users"
        params: list = []
        if platform:
            q += " WHERE platform = ?"
            params.append(platform)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self.db._conn.execute(q, params).fetchall()
        out = []
        for r in rows:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            chat_today = self.db.get_usage(r["id"], "chat", today)
            sub = self.db.get_subscription(r["id"])
            out.append({
                "id": r["id"], "platform": r["platform"], "platform_user_id": r["platform_user_id"],
                "display_name": r["display_name"],
                "created_at": datetime.fromtimestamp(r["created_at"], tz=timezone.utc).isoformat(),
                "messages_today": chat_today,
                "subscription": self._subscription_json(sub),
            })
        return out

    # ---- اشتراک/لایسنس (manual entitlement) --------------------------
    @staticmethod
    def _subscription_json(sub) -> dict | None:
        if not sub:
            return None
        return {
            "plan": sub.plan, "status": sub.status,
            "active_now": sub.is_active_now(),
            "expires_at": (datetime.fromtimestamp(sub.expires_at, tz=timezone.utc).isoformat()
                          if sub.expires_at else None),
            "granted_by": sub.granted_by, "note": sub.note,
        }

    def available_plans(self) -> dict:
        return SUBSCRIPTION_PLANS

    def grant_subscription(self, user_id: int, plan: str, granted_by: str, note: str) -> dict:
        sub = self.db.grant_subscription(user_id, plan, granted_by=granted_by, note=note)
        return self._subscription_json(sub)

    def revoke_subscription(self, user_id: int, performed_by: str, note: str) -> None:
        self.db.revoke_subscription(user_id, performed_by=performed_by, note=note)

    def subscription_history(self, user_id: int) -> list[dict]:
        log = self.db.subscription_audit_log(user_id)
        for row in log:
            row["performed_at"] = datetime.fromtimestamp(row["performed_at"], tz=timezone.utc).isoformat()
        return log

    # ---- تنظیمات (بدون افشای مقدار کامل کلیدها) --------------------
    def settings_snapshot(self) -> dict:
        c = self.cfg
        return {
            "openrouter": {"model": c.openrouter_model, "timeout_s": c.openrouter_timeout_s,
                          "max_retries": c.openrouter_max_retries,
                          "api_key_configured": bool(c.openrouter_api_key),
                          "api_key_preview": mask_secret(c.openrouter_api_key)},
            "telegram": {"admin_id": c.telegram_admin_id or None,
                        "bot_token_configured": bool(c.telegram_bot_token),
                        "bot_token_preview": mask_secret(c.telegram_bot_token)},
            "bale": {"bot_token_configured": bool(c.bale_bot_token),
                    "bot_token_preview": mask_secret(c.bale_bot_token)},
            "rubika": {"bot_token_configured": bool(getattr(c, "rubika_bot_token", "")),
                      "bot_token_preview": mask_secret(getattr(c, "rubika_bot_token", "")),
                      "status": "inactive_pending_confirmation"},
            "db_path": c.db_path,
        }

    # ---- health check — فقط وقتی صریح درخواست شود (نه خودکار) ------
    def check_health(self, target: str) -> dict:
        with self._health_lock:
            if target == "telegram":
                result = self._check_telegram()
            elif target == "bale":
                result = self._check_bale()
            elif target == "openrouter":
                result = self._check_openrouter()
            else:
                return {"ok": False, "error": "هدف نامعتبر"}
            result["checked_at"] = datetime.now(timezone.utc).isoformat()
            self._health_cache[target] = result
            return result

    def last_health(self, target: str) -> dict | None:
        return self._health_cache.get(target)

    def _check_telegram(self) -> dict:
        if not self.cfg.telegram_bot_token:
            return {"ok": False, "checked": True, "error": "BOT_TOKEN تنظیم نشده"}
        sys.path.insert(0, str(ROOT / "apps" / "telegram-bot"))
        from adapter import TelegramAdapter  # noqa: E402 (import دیرهنگام عمدی)
        h = TelegramAdapter(self.cfg.telegram_bot_token).health_check()
        return {"ok": h.ok, "checked": True, "detail": h.detail}

    def _check_bale(self) -> dict:
        if not self.cfg.bale_bot_token:
            return {"ok": False, "checked": True, "error": "BALE_BOT_TOKEN تنظیم نشده"}
        sys.path.insert(0, str(ROOT / "apps" / "bale-bot"))
        from adapter import BaleAdapter  # noqa: E402
        h = BaleAdapter(self.cfg.bale_bot_token).health_check()
        return {"ok": h.ok, "checked": True, "detail": h.detail}

    def _check_openrouter(self) -> dict:
        if not self.cfg.openrouter_api_key:
            return {"ok": False, "checked": True, "error": "OPENROUTER_API_KEY تنظیم نشده"}
        client = OpenRouterClient(OpenRouterConfig(
            api_key=self.cfg.openrouter_api_key, model=self.cfg.openrouter_model,
            timeout_s=min(self.cfg.openrouter_timeout_s, 15), max_retries=0,
        ))
        try:
            reply = client.generate(history=[], prompt="فقط بنویس: pong", system_instruction="خیلی کوتاه پاسخ بده.")
            return {"ok": True, "checked": True, "detail": reply.strip()[:80]}
        except OpenRouterError as e:
            return {"ok": False, "checked": True, "error": e.user_message}

    # ---- چت زنده (همان کلاینت مشترک OpenRouter؛ هیچ تاریخچه‌ای در دیتابیس ذخیره نمی‌شود) --
    def chat(self, message: str, model: str | None, history: list[tuple[str, str]]) -> str:
        if not self.cfg.openrouter_api_key:
            raise OpenRouterError("OPENROUTER_API_KEY تنظیم نشده است.")
        client = OpenRouterClient(OpenRouterConfig(
            api_key=self.cfg.openrouter_api_key, model=(model or self.cfg.openrouter_model),
            timeout_s=self.cfg.openrouter_timeout_s, max_retries=self.cfg.openrouter_max_retries,
        ))
        return client.generate(history=history, prompt=message,
                               system_instruction="شما دستیار هوش مصنوعی پنل مدیریت MODASR هستید.")


class Handler(BaseHTTPRequestHandler):
    state: PanelState  # روی کلاس تنظیم می‌شود (در run_server)
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # لاگ پیش‌فرض noisy را با logging خودمان جایگزین می‌کنیم
        log.info("%s - %s", self.address_string(), fmt % args)

    # ---- کمکی‌ها ----------------------------------------------------
    def _session_token(self) -> str | None:
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = cookies.SimpleCookie()
        jar.load(raw)
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def _require_auth(self) -> bool:
        token = self._session_token()
        if self.state.sessions.is_valid(token):
            return True
        self._send_json(401, {"error": "ورود لازم است"})
        return False

    def _send_json(self, status: int, payload: dict, set_cookie: str | None = None, clear_cookie: bool = False):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if set_cookie:
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}={set_cookie}; HttpOnly; Path=/; SameSite=Strict")
        if clear_cookie:
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; HttpOnly; Path=/; Max-Age=0; SameSite=Strict")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > 1_000_000:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _serve_static(self, path: str):
        if path == "/":
            path = "/index.html"
        safe = os.path.normpath(path).lstrip("/\\")
        full = (STATIC_DIR / safe).resolve()
        if STATIC_DIR not in full.parents and full != STATIC_DIR:
            self.send_response(403)
            self.end_headers()
            return
        if not full.is_file():
            full = STATIC_DIR / "index.html"  # single-page app fallback
        content_type, _ = mimetypes.guess_type(str(full))
        data = full.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---- روتر --------------------------------------------------------
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/me":
                authenticated = self.state.sessions.is_valid(self._session_token())
                return self._send_json(200, {"authenticated": authenticated})
            if path == "/api/dashboard":
                if not self._require_auth():
                    return
                return self._send_json(200, self.state.dashboard_stats())
            if path == "/api/users":
                if not self._require_auth():
                    return
                qs = dict(q.split("=", 1) for q in urlparse(self.path).query.split("&") if "=" in q)
                platform = qs.get("platform") or None
                limit = min(int(qs.get("limit", "50") or 50), 500)
                return self._send_json(200, {"users": self.state.list_users(platform, limit)})
            if path == "/api/subscriptions/plans":
                if not self._require_auth():
                    return
                return self._send_json(200, {"plans": self.state.available_plans()})
            if path.startswith("/api/users/") and path.endswith("/subscription-history"):
                if not self._require_auth():
                    return
                try:
                    user_id = int(path.split("/")[3])
                except (IndexError, ValueError):
                    return self._send_json(400, {"error": "شناسه‌ی کاربر نامعتبر"})
                return self._send_json(200, {"history": self.state.subscription_history(user_id)})
            if path == "/api/settings":
                if not self._require_auth():
                    return
                return self._send_json(200, self.state.settings_snapshot())
            if path.startswith("/api/health/"):
                if not self._require_auth():
                    return
                target = path.rsplit("/", 1)[-1]
                cached = self.state.last_health(target)
                return self._send_json(200, {"target": target, "cached": cached})
            if path == "/api/health":
                if not self._require_auth():
                    return
                return self._send_json(200, {
                    t: self.state.last_health(t) for t in ("telegram", "bale", "openrouter")
                })
            if path.startswith("/api/"):
                return self._send_json(404, {"error": "یافت نشد"})
            return self._serve_static(path)
        except Exception:  # noqa: BLE001
            log.exception("خطای پیش‌بینی‌نشده در GET %s", path)
            return self._send_json(500, {"error": "خطای داخلی سرور"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/login":
                body = self._read_json_body()
                stored_hash = get_admin_password_hash()
                if not stored_hash:
                    return self._send_json(500, {"error": "ADMIN_PASSWORD_HASH در .env تنظیم نشده (اجرا کنید: scripts/set_admin_password.py)"})
                password = str(body.get("password", ""))
                # مقاومت ساده در برابر brute-force: تاخیر ثابت کوچک صرف‌نظر از نتیجه
                time.sleep(0.2)
                if not password or not verify_password(password, stored_hash):
                    return self._send_json(401, {"error": "رمز عبور نادرست است"})
                token = self.state.sessions.create()
                return self._send_json(200, {"ok": True}, set_cookie=token)
            if path == "/api/logout":
                self.state.sessions.destroy(self._session_token())
                return self._send_json(200, {"ok": True}, clear_cookie=True)
            if path.startswith("/api/health/"):
                if not self._require_auth():
                    return
                target = path.rsplit("/", 1)[-1]
                if target not in ("telegram", "bale", "openrouter"):
                    return self._send_json(400, {"error": "هدف نامعتبر"})
                return self._send_json(200, self.state.check_health(target))
            if path.startswith("/api/users/") and path.endswith("/subscription/grant"):
                if not self._require_auth():
                    return
                try:
                    user_id = int(path.split("/")[3])
                except (IndexError, ValueError):
                    return self._send_json(400, {"error": "شناسه‌ی کاربر نامعتبر"})
                body = self._read_json_body()
                plan = str(body.get("plan", ""))
                note = str(body.get("note", ""))[:500]
                try:
                    sub = self.state.grant_subscription(user_id, plan, granted_by="admin-panel", note=note)
                except ValueError as e:
                    return self._send_json(400, {"error": str(e)})
                return self._send_json(200, {"subscription": sub})
            if path.startswith("/api/users/") and path.endswith("/subscription/revoke"):
                if not self._require_auth():
                    return
                try:
                    user_id = int(path.split("/")[3])
                except (IndexError, ValueError):
                    return self._send_json(400, {"error": "شناسه‌ی کاربر نامعتبر"})
                body = self._read_json_body()
                note = str(body.get("note", ""))[:500]
                self.state.revoke_subscription(user_id, performed_by="admin-panel", note=note)
                return self._send_json(200, {"ok": True})
            if path == "/api/chat":
                if not self._require_auth():
                    return
                body = self._read_json_body()
                message = str(body.get("message", "")).strip()
                if not message:
                    return self._send_json(400, {"error": "پیام خالی است"})
                model = body.get("model") or None
                history_raw = body.get("history") or []
                history = [(str(h.get("role")), str(h.get("content"))) for h in history_raw
                          if isinstance(h, dict) and h.get("role") in ("user", "model", "assistant")]
                history = [(("model" if r == "assistant" else r), c) for r, c in history][-16:]
                try:
                    reply = self.state.chat(message, model, history)
                except OpenRouterError as e:
                    return self._send_json(502, {"error": e.user_message})
                return self._send_json(200, {"reply": reply})
            return self._send_json(404, {"error": "یافت نشد"})
        except Exception:  # noqa: BLE001
            log.exception("خطای پیش‌بینی‌نشده در POST %s", path)
            return self._send_json(500, {"error": "خطای داخلی سرور"})


def build_server(cfg: AppConfig | None = None, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    cfg = cfg or AppConfig.load()
    Handler.state = PanelState(cfg)
    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    host = os.environ.get("PANEL_HOST", "127.0.0.1")
    port = int(os.environ.get("PANEL_PORT", "8080"))
    if not get_admin_password_hash():
        log.warning("ADMIN_PASSWORD_HASH تنظیم نشده! تا وقتی تنظیم نکنید، ورود به پنل ممکن نیست. "
                   "اجرا کنید: python3 scripts/set_admin_password.py")
    server = build_server(host=host, port=port)
    log.info("پنل روی http://%s:%s در حال اجراست (Ctrl+C برای توقف)", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
