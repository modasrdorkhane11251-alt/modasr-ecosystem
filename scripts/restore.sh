#!/usr/bin/env bash
# بازیابی از یک فایل پشتیبان ساخته‌شده با backup.sh.
# قبل از رونویسی .env/data فعلی، تایید می‌خواهد (مگر با --yes).
#
# استفاده:
#   bash scripts/restore.sh backups/modasr-backup-20260101-120000.tar.gz
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE="${1:-}"
ASSUME_YES="${2:-}"

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  echo "استفاده: $0 <مسیر-فایل-backup.tar.gz> [--yes]"
  exit 1
fi

echo "⚠️  این عملیات .env و data/ فعلی را با محتوای $ARCHIVE جایگزین می‌کند."
if [ "$ASSUME_YES" != "--yes" ]; then
  read -r -p "برای ادامه 'yes' را تایپ کنید: " confirm
  [ "$confirm" = "yes" ] || { echo "لغو شد."; exit 1; }
fi

echo "توقف سرویس‌ها (در صورت وجود systemd)..."
systemctl stop modasr-telegram modasr-bale modasr-panel modasr-rubika 2>/dev/null || true

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
tar -xzf "$ARCHIVE" -C "$TMP"

[ -f "$TMP/.env" ] && cp "$TMP/.env" "$APP_DIR/.env" && chmod 600 "$APP_DIR/.env"
if [ -d "$TMP/data" ]; then
  rm -rf "$APP_DIR/data"
  cp -r "$TMP/data" "$APP_DIR/data"
fi

echo "✅ بازیابی انجام شد. حالا سرویس‌ها را دوباره راه بیندازید:"
echo "   sudo bash scripts/modasrctl.sh start all"
