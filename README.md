# YouTube Reseam Auto Builder

Repository tự động build YouTube **Non-root** và **Root (Magisk / KernelSU / APatch)** sử dụng [Reseam CLI](https://github.com/Reseam/reseam) và [Reseam Patches](https://github.com/Reseam/patches).

## Cấu trúc thư mục

- `.github/workflows/build-youtube-reseam.yml`: GitHub Actions workflow chính.
- `scripts/get-yt-apk.sh`: Script tải file `youtube.apk` gốc.
- `scripts/build-module.sh`: Đóng gói bản Root thành module flash qua Magisk/KernelSU.
- `config/patches-nonroot.txt` & `config/patches-root.txt`: Tùy biến bật/tắt từng patch.

## Hướng dẫn sử dụng

1. Vào **Settings > Secrets and variables > Actions** của repo, thêm secret `YT_APK_URL` trỏ tới link tải trực tiếp APK YouTube gốc (hoặc nhập trực tiếp khi chạy workflow).
2. Vào tab **Actions** -> chọn **Build YouTube with Reseam** -> bấm **Run workflow**.
3. Sau khi chạy xong, vào mục **Releases** để tải:
   - `youtube-reseam-nonroot.apk`
   - `youtube-reseam-root.apk`
   - `youtube-reseam-root-module.zip`
