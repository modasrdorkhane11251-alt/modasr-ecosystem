# راهنمای نصب و بهره‌برداری (VPS اوبونتو)

## نصب اولیه
```bash
git clone https://github.com/modasrdorkhane11251-alt/modasr-ecosystem.git
cd modasr-ecosystem
sudo bash infra/install.sh
```
این اسکریپت:
- پایتون/venv/rsync را نصب می‌کند
- کاربر سیستمیِ بدون‌دسترسی‌root به نام `modasr` می‌سازد
- کد را به `/opt/modasr-ecosystem` کپی می‌کند (بدون پاک‌کردن `.env`/`data/` موجود از اجرای قبلی)
- اگر `.env` نبود، از `.env.example` می‌سازد (باید دستی پرش کنید)
- وابستگی‌های پایتون را در یک venv نصب می‌کند
- مجوز فایل‌ها را امن می‌کند (`.env` فقط `600`، پوشه‌ی برنامه فقط برای کاربر `modasr`)
- سرویس‌های systemd تلگرام/بله/پنل را نصب، فعال و اجرا می‌کند
- سرویس روبیکا را کپی می‌کند ولی **enable/start نمی‌کند** (تصمیم فعلی پروژه)

بعد از اولین اجرا، `.env` را پر کنید و سرویس‌ها را ری‌استارت کنید:
```bash
sudo nano /opt/modasr-ecosystem/.env
sudo systemctl restart modasr-telegram modasr-bale modasr-panel
```

## به‌روزرسانی (نصب دوباره روی نسخه‌ی جدید کد)
```bash
cd modasr-ecosystem && git pull
sudo bash infra/install.sh
```
چون اسکریپت `.env`، `data/` و `venv/` موجود را از rsync کنار می‌گذارد (`--exclude`)،
این‌ها دست‌نخورده می‌مانند؛ فقط کد و وابستگی‌ها به‌روز می‌شوند.

## دستورهای روزمره
```bash
sudo bash scripts/modasrctl.sh status
sudo bash scripts/modasrctl.sh restart telegram   # یا bale / panel / rubika / all
sudo bash scripts/modasrctl.sh logs bale 200       # ۲۰۰ خط آخر لاگ بله
```
یا مستقیم با `systemctl`/`journalctl`:
```bash
sudo systemctl status modasr-telegram
sudo journalctl -u modasr-telegram -f   # لاگ زنده
```

## راه‌اندازی مجدد خودکار پس از خطا
هر واحد systemd (`infra/systemd/*.service`) این تنظیمات را دارد:
```
Restart=on-failure
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=5
```
یعنی اگر سرویس کرش کند، ۵ ثانیه بعد خودکار بالا می‌آید؛ اگر در ۶۰ ثانیه بیش از ۵ بار
کرش کند، systemd دیگر تلاش نمی‌کند (برای جلوگیری از حلقه‌ی بی‌نهایت) تا دستی بررسی کنید.

## پشتیبان‌گیری و بازیابی
```bash
bash scripts/backup.sh                                    # می‌سازد backups/modasr-backup-<تاریخ>.tar.gz
bash scripts/restore.sh backups/modasr-backup-XXXX.tar.gz  # با تایید دستی
bash scripts/restore.sh backups/modasr-backup-XXXX.tar.gz --yes   # بدون تایید (برای اسکریپت)
```
این دو تابع به‌صورت واقعی (نه فقط خوانده، واقعاً اجرا) تست شدند: یک `.env`/`data` ساختگی
ساخته شد، backup گرفته شد، فایل‌ها خراب شدند، و `restore` محتوای اصلی را درست برگرداند.
فایل backup حاوی `.env` با کلیدهای واقعی است؛ جای امن (نه public) نگه‌دارید.

## امنیت فایل‌ها
- `.env` فقط برای کاربر `modasr` قابل خواندن است (`chmod 600`).
- سرویس‌ها با کاربر سیستمیِ `modasr` اجرا می‌شوند، نه root.
- واحدهای systemd `ProtectSystem=strict`, `ProtectHome=true`, `NoNewPrivileges=true` دارند
  و فقط به `data/` اجازه‌ی نوشتن می‌دهند (`ReadWritePaths`).

## عیب‌یابی رایج
| علامت | احتمال | راه‌حل |
|---|---|---|
| سرویس بالا نمی‌آید، لاگ «پیکربندی ناقص» می‌دهد | `.env` پر نشده | `.env` را پر کنید، سرویس را ری‌استارت کنید |
| «اتصال به تلگرام/بله برقرار نشد» | توکن اشتباه، یا سرور به اینترنت/DNS دسترسی ندارد | با `scripts/test_telegram_connection.py` یا `test_bale_connection.py` جدا تست کنید |
| پنل با ۵۰۰ روی `/api/login` جواب می‌دهد | `ADMIN_PASSWORD_HASH` تنظیم نشده | `python3 scripts/set_admin_password.py` را اجرا کنید |
| `systemctl status` می‌گوید `Failed to connect to bus` | روی یک container بدون systemd واقعی اجرا می‌کنید (نه VPS معمولی) | روی VPS واقعی اجرا کنید؛ این حالت در سندباکس توسعه هم طبیعی است |
| بعد از `git pull` و نصب دوباره، تنظیمات قبلی رفته | بعید — نصب `.env`/`data` را حفظ می‌کند؛ اگر رفته، از آخرین `backups/*.tar.gz` بازیابی کنید | `scripts/restore.sh` |

## ⚠️ آنچه هنوز روی VPS واقعی تست نشده
نصب کامل (`infra/install.sh`) هرگز روی یک Ubuntu تازه با دسترسی root واقعی اجرا نشده؛
فقط نحو (`bash -n`) و واحدهای systemd (`systemd-analyze verify`) تایید شدند. اولین اجرای
واقعی را شما باید انجام دهید و نتیجه (موفق/خطا) را گزارش کنید.
