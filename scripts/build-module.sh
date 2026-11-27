#!/usr/bin/env bash
set -euo pipefail

ROOT_APK="${1:?Thiếu đường dẫn APK root}"
OUTPUT_ZIP="${2:?Thiếu đường dẫn file zip đầu ra}"
YT_VERSION="${3:-latest}"

WORK_MOD="work/module_tmp"
rm -rf "$WORK_MOD"
mkdir -p "$WORK_MOD/META-INF/com/google/android"
mkdir -p "$WORK_MOD/common"

cp "$ROOT_APK" "$WORK_MOD/common/base.apk"

cat <<EOF > "$WORK_MOD/module.prop"
id=yt-reseam-root
name=YouTube Reseam (Root)
version=${YT_VERSION}
versionCode=$(date -u +%Y%m%d)
author=Reseam Builder
description=Systemless YouTube patched with Reseam
EOF

cat <<'EOF' > "$WORK_MOD/post-fs-data.sh"
#!/system/bin/sh
MODDIR=${0%/*}
PKG="com.google.android.youtube"
umount -l "/data/app/"*"/${PKG}-"*"/base.apk" 2>/dev/null
EOF

cat <<'EOF' > "$WORK_MOD/service.sh"
#!/system/bin/sh
MODDIR=${0%/*}
PKG="com.google.android.youtube"

while [ "$(getprop sys.boot_completed)" != "1" ]; do
  sleep 2
done

BASE_PATH=$(pm path "$PKG" | grep "base.apk" | cut -d: -f2 | tr -d '\r')
if [ -n "$BASE_PATH" ] && [ -f "$MODDIR/common/base.apk" ]; then
  chcon u:object_r:apk_data_file:s0 "$MODDIR/common/base.apk" 2>/dev/null
  mount -o bind "$MODDIR/common/base.apk" "$BASE_PATH"
fi
EOF

cat <<'EOF' > "$WORK_MOD/META-INF/com/google/android/update-binary"
#!/sbin/sh
umask 022
ui_print() { echo "$1"; }
OUTFD=$2
ZIPFILE=$3
mount /data 2>/dev/null
. /data/adb/magisk/util_functions.sh 2>/dev/null || exit 1
install_module
exit 0
EOF

echo "#MAGISK" > "$WORK_MOD/META-INF/com/google/android/updater-script"

chmod +x "$WORK_MOD/post-fs-data.sh" "$WORK_MOD/service.sh" "$WORK_MOD/META-INF/com/google/android/update-binary"

mkdir -p "$(dirname "$OUTPUT_ZIP")"
ABS_OUT="$(realpath "$OUTPUT_ZIP")"
(cd "$WORK_MOD" && zip -r9 "$ABS_OUT" .)
echo "Created root module: $OUTPUT_ZIP"
