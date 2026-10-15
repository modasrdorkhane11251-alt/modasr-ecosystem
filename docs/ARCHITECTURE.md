# معماری (مونولیت ماژولار؛ بدون میکروسرویس غیرضروری)

```
packages/core/
  config.py              بارگذاری/اعتبارسنجی env از .env؛ بدون مقدار پیش‌فرض خطرناک
  database.py             SQLite + مهاجرت نسخه‌دار (user_version)؛ هویت = (platform, platform_user_id)
  platform_adapter.py      اینترفیس انتزاعی مشترک همه‌ی پیام‌رسان‌ها
  ai/openrouter.py          کلاینت OpenRouter — ارائه‌دهنده‌ی اصلی و فعال هوش مصنوعی
  ai/gemini.py               کلاینت Gemini — نگه‌داشته‌شده به‌عنوان ارائه‌دهنده‌ی اختیاری/غیرفعال

apps/telegram-bot/   adapter.py + main.py (polling واقعی)
apps/bale-bot/        adapter.py + main.py (polling مستقل، پردازه‌ی جدا از تلگرام)
apps/rubika-bot/       adapter.py + main.py — کد کامل است، اما به‌صورت پیش‌فرض در
                       infra/install.sh enable/start نمی‌شود (پایین را ببینید)

apps/web-panel/
  server.py             JSON API روی http.server استاندارد پایتون (بدون Flask)
  auth.py                 هش رمز PBKDF2 + نشست‌های سمت سرور (SessionStore در حافظه)
  static/                 فرانت‌اند خالص HTML/CSS/JS، RTL فارسی، بدون مرحله‌ی build

infra/
  install.sh              نصب Ubuntu (کاربر غیرroot، venv، systemd، مجوز فایل امن)
  systemd/*.service        واحدهای تلگرام/بله/پنل/روبیکا

scripts/
  modasrctl.sh, backup.sh, restore.sh, check_secrets.py,
  set_admin_password.py, test_{openrouter,telegram,bale}_live.py,
  test_{telegram,bale}_connection.py
```

## ارائه‌دهنده‌ی هوش مصنوعی (تصمیم فعلی پروژه)
- **OpenRouter ارائه‌دهنده‌ی اصلی و فعال است**، روی `POST /api/v1/chat/completions`
  (فرمت سازگار با OpenAI: `messages[]`, `choices[0].message.content`).
- تلگرام، بله، روبیکا، و پنل وب (صفحه‌ی چت) هر چهار از همین یک ماژول
  `packages/core/ai/openrouter.py` استفاده می‌کنند — نه کپی جدا در هرکدام.
- `gemini.py` حذف نشده (طبق تصمیم صریح پروژه)، ولی هیچ کد تولیدی فعلی آن را صدا نمی‌زند.
- متغیرهای تنظیم: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_TIMEOUT_S`,
  `OPENROUTER_MAX_RETRIES` (در `packages/core/config.py`).

## پیام‌رسان‌ها
- منطق AI و دیتابیس هیچ‌وقت مستقیم با SDK یک پیام‌رسان کار نمی‌کند؛ فقط از پشت
  `PlatformAdapter`. هر `main.py` پردازه‌ی خودش را دارد (سه دستور `python` جدا).
- هویت کاربر بر اساس `(platform, platform_user_id)` است، نه فقط یک ID خام.
  اتصال صریح حساب‌ها بین پلتفرم‌ها (account linking) هنوز اضافه نشده.
- **روبیکا**: آداپتور (`apps/rubika-bot/adapter.py`) با `botapi.rubika.ir/v3/<token>`
  کار می‌کند — یعنی لاگین با توکن ربات، نه شماره‌تلفن/کد پیامکیِ یک اکانت شخصی. این با
  نگرانی اولیه‌ی پروژه («API غیررسمی متصل به حساب شخصی») فرق دارد، ولی این تفاوت در این
  محیط توسعه با مستندات رسمی روبیکا تایید نشده (فقط از شکل کد قابل استنتاج است). طبق
  تصمیم صریح پروژه، تا تایید نهایی شما، سرویس روبیکا در نصب خودکار enable/start نمی‌شود
  (`infra/install.sh` عمداً آن را از لیست سرویس‌های فعال کنار گذاشته).

## پنل مدیریت وب
کتابخانه‌ی خارجی (Flask/FastAPI) استفاده نشده چون نصب پکیج جدید در محیط توسعه ممکن نبود؛
`http.server.ThreadingHTTPServer` با یک router دستی کل API را پیاده می‌کند. اگر روی
سرور خودتان ترجیح می‌دهید Flask به‌کار ببرید، می‌توانید `server.py` را جایگزین کنید؛
قرارداد API همین است و بقیه‌ی پروژه (frontend) به آن وابسته است، نه به این پیاده‌سازی خاص.

### API (همه نیازمند کوکی نشست معتبر `modasr_session` هستند، مگر login/logout)
| مسیر | متد | کار |
|---|---|---|
| `/api/login` | POST | `{password}` → تایید با `ADMIN_PASSWORD_HASH`، ست‌کردن کوکی نشست |
| `/api/logout` | POST | ابطال نشست |
| `/api/me` | GET | `{authenticated: bool}` |
| `/api/dashboard` | GET | آمار واقعی از دیتابیس: کاربران به تفکیک پلتفرم، مصرف امروز |
| `/api/users` | GET | `?platform=&limit=` لیست کاربران واقعی |
| `/api/settings` | GET | تنظیمات غیرمحرمانه + پیش‌نمایش کوتاه کلیدها (نه مقدار کامل) |
| `/api/health/<target>` | POST | health check **زنده** (`telegram`/`bale`/`openrouter`)، فقط وقتی صریح درخواست شود |
| `/api/health` | GET | آخرین نتیجه‌ی کش‌شده‌ی health checkها (بدون زدن شبکه) |
| `/api/chat` | POST | `{message, model?, history?}` → چت زنده با OpenRouter (تاریخچه در دیتابیس ذخیره نمی‌شود) |
| `/api/subscriptions/plans` | GET | لیست پلن‌های تعریف‌شده (`packages/core/database.py:SUBSCRIPTION_PLANS`) |
| `/api/users/<id>/subscription/grant` | POST | `{plan, note?}` → صدور/تمدید اشتراک دستی (manual entitlement) |
| `/api/users/<id>/subscription/revoke` | POST | `{note?}` → لغو اشتراک فعال |
| `/api/users/<id>/subscription-history` | GET | تاریخچه‌ی کامل grant/renew/revoke آن کاربر |

### اشتراک/لایسنس (فقط manual entitlement — بدون درگاه پرداخت واقعی)
طبق تصمیم صریح پروژه، هیچ درگاه پرداختی وصل نشده. جدول `subscriptions` یک ردیب فعال
به ازای هر کاربر نگه می‌دارد (grant دوباره = تمدید/تغییر پلن همان ردیف)، و
`subscription_audit_log` تاریخچه‌ی کامل (هیچ‌وقت پاک نمی‌شود) را ثبت می‌کند. پلن‌ها
در `SUBSCRIPTION_PLANS` تعریف شده‌اند (رایگان/ماهانه/سه‌ماهه/شش‌ماهه/یک‌ساله/دائمی)؛
فقط نام و مدت دارند، نه قیمت یا منطق پرداخت. صدور/لغو فعلاً فقط از پنل مدیریت ممکن
است (`admin-panel` به‌عنوان `granted_by` ثبت می‌شود).

هر دو `apps/telegram-bot/main.py` و `apps/bale-bot/main.py` تابع `check_quota` را
دارند (کد یکسان، عمداً کپی نه import مشترک، چون این دو پردازه‌ی کاملاً مستقل‌اند):
کاربرِ بدون اشتراک فعال با سقف پلن `free` (پیش‌فرض ۲۰ پیام در روز) محدود می‌شود؛
کاربرِ دارای اشتراکِ فعال (غیر از `free`) نامحدود است. اشتراک لغوشده یا منقضی‌شده
خودکار به سقف `free` برمی‌گردد. پلن نامعتبر/ناشناس در دیتابیس محافظه‌کارانه رد
می‌شود (نه کرش، نه نامحدودِ ساکت).

احراز هویت: PBKDF2 (۲۶۰٬۰۰۰ تکرار) + نشست تصادفی سمت سرور با انقضا (۸ ساعت)، کوکی
`HttpOnly`. رمز خام هیچ‌جا ذخیره/چاپ نمی‌شود (`scripts/set_admin_password.py`).
بدون TLS داخلی؛ در تولید باید پشت reverse proxy با HTTPS واقعی باشد.

## وضعیت لایه‌های آینده
اشتراک/لایسنس/پرداخت واقعی هنوز شروع نشده (طبق اولویت‌بندی فعلی پروژه: ابتدا پنل، VPS،
و GitHub). جزئیات و ترتیب در `docs/NEXT_STEPS.md`.
