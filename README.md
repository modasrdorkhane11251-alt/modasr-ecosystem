# MODASR ECOSYSTEM — هسته (نسخه‌ی اولیه)

وضعیت واقعی و دقیق این نسخه در `docs/TEST_REPORT.md` و `docs/NEXT_STEPS.md` است؛ همین‌جا فقط خلاصه.

## چی کار می‌کند (تست‌شده با mock، نه زنده)
- هسته‌ی پیکربندی و دیتابیس SQLite (مهاجرت نسخه‌دار، چند پلتفرم، حافظه‌ی مکالمه، شمارش مصرف روزانه)
- کلاینت Gemini با مدیریت کامل خطا (400/401/403/404/429/5xx) و retry با backoff
- اینترفیس مشترک آداپتور پیام‌رسان (`PlatformAdapter`)
- آداپتور تلگرام کامل (پارس پیام متنی/عکس/ویس/ویدیو/callback، ارسال پیام، health check)
- آداپتور بله کامل، به همان شکل، روی `tapi.bale.ai` (مطابق مستندات رسمی بله)
- حلقه‌ی اجرای واقعی تلگرام (`apps/telegram-bot/main.py`) که همه‌ی این‌ها را به هم وصل می‌کند

## چی کار نمی‌کند / عمداً ناقص است
- **روبیکا**: پیاده نشده. روبیکا API رسمی ربات ندارد؛ جزئیات و دلیل در `apps/rubika-bot/adapter.py` و `docs/NEXT_STEPS.md`.
- هیچ تست زنده‌ای (اتصال واقعی به Gemini/تلگرام/بله) در این محیط اجرا نشده، چون اینجا اینترنت نیست.
- وب‌اپ، پنل ادمین، اشتراک/پرداخت، لایسنس: هنوز شروع نشده (طبق ترتیبی که خواسته بودید).

## اجرا روی سرور خودتان
```bash
cd modasr-ecosystem
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # BOT_TOKEN و GEMINI_API_KEY را پر کنید
python apps/telegram-bot/main.py
```

## اجرای تست‌ها
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
انتظار: ۴۷ تست، همه PASS (نتیجه‌ی واقعی اجراشده در `docs/TEST_REPORT.md`).

## ساختار
```
packages/core/          منطق مشترک: config, database, platform_adapter, ai/gemini
apps/telegram-bot/      آداپتور تلگرام + حلقه‌ی اجرا (main.py)
apps/bale-bot/          آداپتور بله (adapter.py)
apps/rubika-bot/        اسکلت مسدود؛ نیاز به تصمیم شما
tests/                  unittest، روی هر فایل بالا
docs/                   اسناد مهندسی (پایین)
```
