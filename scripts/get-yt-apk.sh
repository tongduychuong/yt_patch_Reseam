#!/usr/bin/env bash
set -euo pipefail

YT_VERSION="${1:-}"
OUTPUT_APK="${2:-work/apk/youtube.apk}"
INPUT_URL="${3:-}"
SECRET_URL="${4:-}"

mkdir -p "$(dirname "$OUTPUT_APK")"

DOWNLOAD_URL="${INPUT_URL:-$SECRET_URL}"

if [ -n "$DOWNLOAD_URL" ]; then
  echo "Downloading YouTube APK from provided URL..."
  curl -fSL -A "Mozilla/5.0" "$DOWNLOAD_URL" -o "$OUTPUT_APK"
else
  echo "ERROR: Chưa cấu hình nguồn tải APK."
  echo "Hãy truyền 'apk_url' khi chạy workflow_dispatch hoặc thiết lập Secret 'YT_APK_URL' trong repo."
  exit 1
fi

if [ ! -s "$OUTPUT_APK" ]; then
  echo "ERROR: File APK tải về bị rỗng."
  exit 1
fi

echo "Base APK ready at: $OUTPUT_APK ($(du -h "$OUTPUT_APK" | cut -f1))"
