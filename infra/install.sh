#!/usr/bin/env bash
# نصب MODASR ECOSYSTEM روی Ubuntu (۲۲.۰۴ یا ۲۴.۰۴ تست‌شده با apt؛ نسخه‌های دیگر Ubuntu
# احتمالاً کار می‌کنند ولی تست نشده‌اند. این اسکریپت idempotent است: اجرای دوباره‌اش
# .env و data/ موجود را پاک نمی‌کند، فقط کد و وابستگی‌ها را به‌روز می‌کند.
#
# اجرا (به‌عنوان root یا با sudo):
#   sudo bash infra/install.sh
#
# ⚠️ این اسکریپت روی این سندباکس اجرا/تست نشده (اینجا systemd واقعی در حال اجرا نیست و
# دسترسی root/apt کامل نیست). قبل از اعتماد کامل، یک بار روی یک VPS تست Ubuntu تازه
# اجرا کنید و نتیجه را گزارش کنید.
set -euo pipefail

APP_USER="modasr"
APP_DIR="/opt/modasr-ecosystem"
SERVICE_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # ریشه‌ی ریپو که این اسکریپت از آن اجرا می‌شود
SYSTEMD_DIR="/etc/systemd/system"

if [ "$(id -u)" -ne 0 ]; then
  echo "❌ این اسکریپت باید با root یا sudo اجرا شود." >&2
  exit 1
fi

echo "== ۱) وابستگی‌های سیستمی =="
apt-get update -y
apt-get install -y python3 python3-venv python3-pip rsync

echo "== ۲) کاربر سرویس (بدون دسترسی root) =="
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
  echo "کاربر سیستمی $APP_USER ساخته شد."
else
  echo "کاربر $APP_USER از قبل وجود دارد."
fi

echo "== ۳) کپی کد به $APP_DIR (بدون پاک‌کردن .env/data موجود) =="
mkdir -p "$APP_DIR"
rsync -a --delete \
  --exclude ".env" --exclude ".env.bak" --exclude "data/" --exclude "venv/" \
  --exclude ".git/" --exclude "__pycache__/" --exclude "*.pyc" \
  "$SERVICE_SRC_DIR"/ "$APP_DIR"/
mkdir -p "$APP_DIR/data"

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "⚠️  .env تازه از روی .env.example ساخته شد. حتماً قبل از اجرا پرش کنید:"
  echo "    nano $APP_DIR/.env"
else
  echo ".env موجود دست‌نخورده نگه داشته شد."
fi

echo "== ۴) محیط مجازی پایتون و وابستگی‌ها =="
if [ ! -d "$APP_DIR/venv" ]; then
  python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --upgrade pip --quiet
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" --quiet

echo "== ۵) مجوز فایل‌ها =="
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 750 "$APP_DIR"
[ -f "$APP_DIR/.env" ] && chmod 600 "$APP_DIR/.env"
chmod 750 "$APP_DIR/data"

echo "== ۶) نصب سرویس‌های systemd (تلگرام، بله، پنل — روبیکا عمداً فعال نمی‌شود) =="
for svc in modasr-telegram modasr-bale modasr-panel; do
  cp "$APP_DIR/infra/systemd/${svc}.service" "$SYSTEMD_DIR/${svc}.service"
done
# سرویس روبیکا کپی می‌شود تا در دسترس باشد، ولی enable/start نمی‌شود — طبق تصمیم فعلی پروژه
cp "$APP_DIR/infra/systemd/modasr-rubika.service" "$SYSTEMD_DIR/modasr-rubika.service"

systemctl daemon-reload

echo "== ۷) فعال‌سازی و شروع سرویس‌ها =="
for svc in modasr-telegram modasr-bale modasr-panel; do
  systemctl enable "$svc"
  systemctl restart "$svc"
done

echo
echo "✅ نصب تمام شد."
echo "   - وضعیت: sudo bash $APP_DIR/scripts/modasrctl.sh status"
echo "   - روبیکا عمداً enable/start نشد. وقتی تصمیم نهایی گرفتید:"
echo "       sudo systemctl enable --now modasr-rubika"
echo "   - اگر .env تازه ساختید، حتماً پرش کنید و سرویس‌ها را ری‌استارت کنید:"
echo "       sudo systemctl restart modasr-telegram modasr-bale modasr-panel"
