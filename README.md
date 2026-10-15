# MODASR ECOSYSTEM

دستیار هوش مصنوعی چندپیام‌رسانی (تلگرام، بله، و به‌صورت غیرفعال/در انتظار تایید: روبیکا)
با هسته‌ی هوش مصنوعی مشترک OpenRouter، به‌علاوه‌ی پنل مدیریت وب.

**وضعیت واقعی و دقیق پروژه (چه چیزی تست زنده شده، چه چیزی نشده) همیشه در
[`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) و [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md)
است؛ این README فقط خلاصه و راهنمای اجراست.** For English, see [`README.en.md`](README.en.md).

## معماری خیلی خلاصه
```
packages/core/          هسته‌ی مشترک: config, database (SQLite), platform_adapter, ai/openrouter
apps/telegram-bot/      آداپتور تلگرام + حلقه‌ی اجرا (main.py)
apps/bale-bot/          آداپتور بله + حلقه‌ی اجرا (main.py)
apps/rubika-bot/        آداپتور + حلقه‌ی اجرای روبیکا — کد موجود است، ولی systemd آن را
                         به‌صورت پیش‌فرض enable/start نمی‌کند (جزئیات در docs/NEXT_STEPS.md)
apps/web-panel/         پنل مدیریت (backend با کتابخانه‌ی استاندارد پایتون + فرانت‌اند
                         استاتیک HTML/CSS/JS فارسی RTL، بدون مرحله‌ی build)
infra/                  systemd units + اسکریپت نصب Ubuntu
scripts/                ابزارهای کمکی: کنترل سرویس‌ها، پشتیبان‌گیری، تست‌های زنده، امنیت
tests/                  مجموعه‌ی تست unittest برای تمام موارد بالا
docs/                   اسناد مهندسی (معماری، امنیت، گزارش تست، قدم‌های بعدی)
```

هسته‌ی هوش مصنوعی **OpenRouter** است (`packages/core/ai/openrouter.py`)؛ تلگرام، بله، و
روبیکا هر سه از همین یک کلاینت مشترک استفاده می‌کنند، نه کپی جدا در هر ربات. Gemini
(`packages/core/ai/gemini.py`) به‌عنوان ارائه‌دهنده‌ی اختیاری/غیرفعال نگه داشته شده؛
هیچ ربات فعلی آن را صدا نمی‌زند.

## نصب سریع (توسعه/تست محلی)
```bash
git clone https://github.com/modasrdorkhane11251-alt/modasr-ecosystem.git
cd modasr-ecosystem
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # حداقل OPENROUTER_API_KEY و BOT_TOKEN (یا BALE_BOT_TOKEN) را پر کنید

python3 -m unittest discover -s tests -p "test_*.py" -v   # باید همه PASS بدهد

python3 scripts/test_openrouter_live.py        # تست زنده‌ی OpenRouter (نیاز به کلید واقعی)
python3 scripts/test_telegram_connection.py    # تست زنده‌ی تلگرام
python3 scripts/test_bale_connection.py        # تست زنده‌ی بله

python3 apps/telegram-bot/main.py   # اجرای واقعی (polling)؛ هر ربات را در ترمینال/سرویس جدا اجرا کنید
```

## پنل مدیریت وب
```bash
python3 scripts/set_admin_password.py     # رمز عبور مدیر را می‌سازد (خودِ رمز چاپ نمی‌شود)
# خروجی را به‌عنوان ADMIN_PASSWORD_HASH در .env بگذارید
python3 apps/web-panel/server.py
# http://127.0.0.1:8080
```
پنل داشبورد واقعی (آمار از دیتابیس)، چت زنده با OpenRouter، مدیریت کاربران، و وضعیت
اتصال هر پیام‌رسان را نشان می‌دهد. جزئیات API در [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
در تولید، این سرور (که TLS ندارد) را پشت nginx/Caddy با HTTPS واقعی بگذارید.

## نصب روی VPS اوبونتو (تولید)
```bash
sudo bash infra/install.sh
sudo bash scripts/modasrctl.sh status
sudo bash scripts/modasrctl.sh logs telegram 200
```
جزئیات کامل، شامل پشتیبان‌گیری/بازیابی و عیب‌یابی، در
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
⚠️ این اسکریپت‌ها در محیط توسعه (بدون systemd واقعی/root) قابل اجرای کامل نبودند؛
واحدهای systemd با `systemd-analyze verify` بررسی شدند و توابع پشتیبان‌گیری/بازیابی
به‌صورت واقعی تست شدند (جزئیات در `docs/TEST_REPORT.md`)، ولی **کل فرایند نصب روی یک
VPS واقعی هنوز توسط شما تست نشده.**

## قبل از انتشار روی GitHub
```bash
python3 scripts/check_secrets.py
```
این دستور فایل‌های track‌شده‌ی git را برای چیزهای شبیه کلید/توکن واقعی می‌گردد. در
GitHub Actions هم خودکار اجرا می‌شود (`.github/workflows/tests.yml`).

## مستندات کامل
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — معماری، تصمیم ارائه‌دهنده‌ی AI، API پنل
- [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md) — یافته‌های امنیتی
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — نصب VPS، systemd، پشتیبان‌گیری، عیب‌یابی
- [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) — نتیجه‌ی واقعی هر دور تست
- [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md) — وضعیت فعلی هر بخش و کارهای باقی‌مانده
