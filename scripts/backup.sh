#!/usr/bin/env bash
# پشتیبان‌گیری از .env و دیتابیس. خروجی: فایل tar.gz با تاریخ، در پوشه‌ی backups/.
#
# استفاده:
#   bash scripts/backup.sh                 # در /opt/modasr-ecosystem/backups می‌سازد
#   BACKUP_DIR=/path/other bash scripts/backup.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/modasr-backup-$STAMP.tar.gz"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

[ -f "$APP_DIR/.env" ] && cp "$APP_DIR/.env" "$TMP/.env"
if [ -d "$APP_DIR/data" ]; then
  cp -r "$APP_DIR/data" "$TMP/data"
fi

tar -czf "$OUT" -C "$TMP" .
chmod 600 "$OUT"

echo "✅ پشتیبان ساخته شد: $OUT"
echo "   این فایل حاوی .env (با کلیدهای واقعی) است؛ جایی خارج از سرور با احتیاط نگه دارید."
