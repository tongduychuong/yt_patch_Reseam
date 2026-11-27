import os
import sys
import subprocess
import shutil
import urllib.parse
import time
import re


# ============================================================
# CONFIG
# ============================================================

def read_version_from_txt(app_name: str) -> str:
    txt_name = "youtube_music.txt" if app_name in ("ytm", "youtube-music") else "youtube.txt"
    search_paths = [
        txt_name,
        os.path.join("..", txt_name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", txt_name),
    ]
    for path in search_paths:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                ver = f.read().strip()
                if ver:
                    return ver
    return ""


raw_arg2 = (sys.argv[2] if len(sys.argv) > 2 else "").strip()
raw_arg3 = (sys.argv[3] if len(sys.argv) > 3 else "").strip()

app_key = (os.environ.get("APP") or (sys.argv[1] if len(sys.argv) > 1 else "youtube")).strip().lower()

# Hỗ trợ truyền trực tiếp version, đường dẫn file (../youtube.txt), hoặc tự đọc từ youtube.txt / youtube_music.txt
if raw_arg2 and os.path.isfile(raw_arg2):
    with open(raw_arg2, "r", encoding="utf-8") as f:
        version = f.read().strip()
    output_filename = raw_arg3
elif raw_arg2 and raw_arg2.lower() != "auto":
    version = os.environ.get("VERSION", "").strip() or raw_arg2
    output_filename = raw_arg3
else:
    version = (os.environ.get("VERSION") or read_version_from_txt(app_key)).strip()
    output_filename = raw_arg2 if (raw_arg2 and not raw_arg2.lower() == "auto") else raw_arg3

APP_CONFIG = {
    "youtube": {
        "label": "YouTube",
        "pkg": "com.google.android.youtube",
        "dir_prefix": "google-inc/youtube/youtube",
        "slug_prefix": "youtube",
        "default_out": "youtube.apk",
    },
    "ytm": {
        "label": "YouTube Music",
        "pkg": "com.google.android.apps.youtube.music",
        "dir_prefix": "google-inc/youtube-music/youtube-music",
        "slug_prefix": "youtube-music",
        "default_out": "youtube-music.apk",
    },
    "youtube-music": {
        "label": "YouTube Music",
        "pkg": "com.google.android.apps.youtube.music",
        "dir_prefix": "google-inc/youtube-music/youtube-music",
        "slug_prefix": "youtube-music",
        "default_out": "youtube-music.apk",
    },
}

if app_key not in APP_CONFIG:
    print(f"ERROR: Unsupported APP '{app_key}'. Use 'youtube' or 'ytm'.")
    sys.exit(1)

if not version:
    print("ERROR: VERSION is missing (not passed and not found in youtube.txt / youtube_music.txt)")
    sys.exit(1)

cfg = APP_CONFIG[app_key]
if not output_filename:
    output_filename = cfg["default_out"]

BASE = "https://www.apkmirror.com"
V = version.replace(".", "-")
UA = "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 Chrome/140.0.0.0 Mobile Safari/537.36"


# ============================================================
# HELPERS
# ============================================================

def sleep(sec):
    time.sleep(sec)


def wget(url):
    try:
        result = subprocess.run(
            [
                "wget",
                "-q",
                "--max-redirect=10",
                "--timeout=60",
                "--tries=3",
                "-U",
                UA,
                url,
                "-O",
                "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        return result.stdout
    except Exception as e:
        print(f"wget error: {e}")
        return ""


def download(url, filename):
    subprocess.run(
        [
            "wget",
            "-q",
            "--show-progress",
            "--max-redirect=10",
            "--timeout=180",
            "--tries=5",
            "-U",
            UA,
            url,
            "-O",
            filename
        ],
        check=True
    )


def clean_url(url):
    if not url:
        return url
    return (
        url
        .replace("&amp;", "&")
        .replace("amp;", "")
        .strip()
    )


def absolute_url(url, base):
    url = clean_url(url)
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("//"):
        return "https:" + url
    return urllib.parse.urljoin(base, url)


# ============================================================
# APKMIRROR PARSERS
# ============================================================

def find_download_button(html):
    if not html:
        return None

    patterns = [
        r'downloadButton[\s\S]{0,2000}?href=["\']([^"\']+)["\']',
        r'<a[^>]*class=["\'][^"\']*downloadButton[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
        r'<a[^>]*href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*downloadButton[^"\']*["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match and match.group(1):
            return clean_url(match.group(1))

    return None


def find_here(html):
    if not html:
        return None

    patterns = [
        r'href=["\']([^"\']+)["\'][^>]*>\s*here\s*<',
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*here\s*</a>',
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[\s\S]{0,300}?\bhere\b[\s\S]{0,300}?</a>',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match and match.group(1):
            return clean_url(match.group(1))

    return None


# ============================================================
# FILE VALIDATION
# ============================================================

def check_file(filename):
    if not os.path.exists(filename):
        return "invalid"

    try:
        result = subprocess.run(
            ["unzip", "-l", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )

        out = result.stdout
        if result.returncode != 0:
            return "invalid"

        if "base.apk" in out or "splits/" in out or "split_config." in out:
            return "bundle"

        if "AndroidManifest.xml" in out:
            return "apk"

    except Exception as e:
        print(f"File check error: {e}")

    return "invalid"


# ============================================================
# CANDIDATE PROCESSOR
# ============================================================

def candidate(relative_path, number, total):
    page = f"{BASE}/apk/{relative_path}"
    temp = f"{app_key}-{number}.tmp"

    print()
    print("======================================")
    print(f"CANDIDATE {number}/{total}")
    print(page)
    print("======================================")

    try:
        html = wget(page)
        if not html:
            raise Exception("Không tải được APKMirror page")

        print("\nWaiting 15 seconds for downloadButton...")
        for i in range(15, 0, -1):
            sys.stdout.write(f"\rWaiting {i}s...")
            sys.stdout.flush()
            sleep(1)
        print()

        button = find_download_button(html)
        retry = 0
        while not button and retry < 15:
            retry += 1
            print(f"Retry downloadButton {retry}/15...")
            sleep(1)
            html = wget(page)
            button = find_download_button(html)

        if not button:
            raise Exception("Không tìm thấy downloadButton")

        download_page = absolute_url(button, page)
        if not download_page:
            raise Exception("Download page URL không hợp lệ")

        print("\nDOWNLOAD PAGE:")
        print(download_page)

        html2 = wget(download_page)
        if not html2:
            raise Exception("Không tải được download page")

        print("\nWaiting 15 seconds for 'here'...")
        for i in range(15, 0, -1):
            sys.stdout.write(f"\rWaiting {i}s...")
            sys.stdout.flush()
            sleep(1)
        print()

        real_url = find_here(html2)
        retry = 0
        while not real_url and retry < 15:
            retry += 1
            print(f"Retry final URL {retry}/15...")
            sleep(1)
            html2 = wget(download_page)
            real_url = find_here(html2)

        if not real_url:
            raise Exception("Không tìm thấy link here")

        real_url = absolute_url(real_url, download_page)
        if not real_url:
            raise Exception("Final download URL không hợp lệ")

        print("\nREAL DOWNLOAD:")
        print(real_url)

        if os.path.exists(temp):
            os.remove(temp)

        print("\nDownloading APK...")
        download(real_url, temp)

        file_type = check_file(temp)
        print("\nFILE TYPE:", file_type)

        if file_type == "bundle":
            print("Bundle detected - skip.")
            if os.path.exists(temp):
                os.remove(temp)
            return False

        if file_type != "apk":
            print("Invalid APK - skip.")
            if os.path.exists(temp):
                os.remove(temp)
            return False

        if os.path.exists(output_filename):
            os.remove(output_filename)

        shutil.move(temp, output_filename)
        size_mb = os.path.getsize(output_filename) / 1024 / 1024

        print()
        print("======================================")
        print("NORMAL APK FOUND")
        print("======================================")
        print("FILE:", output_filename)
        print("SIZE:", f"{size_mb:.2f} MB")
        print()

        return True

    except Exception as error:
        print()
        print(f"Candidate {number} failed: {error}")
        if os.path.exists(temp):
            try:
                os.remove(temp)
            except Exception:
                pass
        return False


# ============================================================
# MAIN
# ============================================================

def main():
    prefix_dir = f"{cfg['dir_prefix']}-{V}-release"
    slug = f"{cfg['slug_prefix']}-{V}"

    candidates = [
        f"{prefix_dir}/{slug}-2-android-apk-download/",
        f"{prefix_dir}/{slug}-android-apk-download/",
        f"{prefix_dir}/{slug}-3-android-apk-download/",
        f"{prefix_dir}/{slug}-4-android-apk-download/",
    ]

    print("======================================")
    print(f"{cfg['label']} APKMirror Downloader")
    print("======================================")
    print("PACKAGE:", cfg["pkg"])
    print("VERSION:", version)
    print("OUTPUT:", output_filename)
    print("======================================")

    for i, path in enumerate(candidates, start=1):
        if candidate(path, i, len(candidates)):
            return

    raise Exception(f"Không tìm thấy NORMAL APK cho {cfg['label']} {version}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nERROR: Interrupted by user")
        sys.exit(130)
    except Exception as error:
        print("\n======================================")
        print("ERROR:", error)
        print("======================================")
        sys.exit(1)
