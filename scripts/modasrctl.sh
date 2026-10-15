#!/usr/bin/env bash
# دستورهای روزمره‌ی مدیریت سرویس‌های MODASR. اجرا با sudo.
#
# استفاده:
#   sudo bash scripts/modasrctl.sh status
#   sudo bash scripts/modasrctl.sh start|stop|restart [telegram|bale|panel|rubika|all]
#   sudo bash scripts/modasrctl.sh logs <telegram|bale|panel|rubika> [تعداد خط، پیش‌فرض ۱۰۰]
#
# ⚠️ در این سندباکس تست نشده (systemd واقعی اینجا در حال اجرا نیست).
set -euo pipefail

SERVICES=(telegram bale panel rubika)

svc_name() { echo "modasr-$1"; }

usage() {
  echo "استفاده: $0 status | start|stop|restart [${SERVICES[*]}|all] | logs <${SERVICES[*]}> [خطوط]"
  exit 1
}

[ $# -ge 1 ] || usage
cmd="$1"; shift || true

case "$cmd" in
  status)
    for s in "${SERVICES[@]}"; do
      echo "— $(svc_name "$s") —"
      systemctl status "$(svc_name "$s")" --no-pager -l | head -5 || true
      echo
    done
    ;;
  start|stop|restart)
    target="${1:-all}"
    if [ "$target" = "all" ]; then
      targets=("${SERVICES[@]}")
    else
      targets=("$target")
    fi
    for s in "${targets[@]}"; do
      echo "در حال $cmd کردن $(svc_name "$s")..."
      systemctl "$cmd" "$(svc_name "$s")"
    done
    echo "انجام شد. وضعیت را با 'status' بررسی کنید."
    ;;
  logs)
    [ $# -ge 1 ] || usage
    target="$1"
    lines="${2:-100}"
    journalctl -u "$(svc_name "$target")" -n "$lines" --no-pager
    ;;
  *)
    usage
    ;;
esac
