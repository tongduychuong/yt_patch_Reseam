import argparse
import os
import re
import sys
import urllib.parse
import urllib.request
import zipfile


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

APP_CONFIG = {
    "youtube": {
        "pkg": "com.google.android.youtube",
        "slug": "youtube",
    },
    "yt": {
        "pkg": "com.google.android.youtube",
        "slug": "youtube",
    },
    "ytm": {
        "pkg": "com.google.android.apps.youtube.music",
        "slug": "youtube-music",
    },
    "music": {
        "pkg": "com.google.android.apps.youtube.music",
        "slug": "youtube-music",
    },
}


def resolve_version(app_key: str, version_arg: str) -> str:
    val = (version_arg or "").strip()

    # Nếu truyền vào là đường dẫn file (ví dụ: ../youtube.txt hoặc youtube.txt)
    if val and os.path.isfile(val):
        with open(val, "r", encoding="utf-8") as f:
            ver = f.read().strip()
            if ver:
                return ver
            raise ValueError(f"File phiên bản '{val}' đang rỗng.")

    # Nếu truyền chuỗi phiên bản trực tiếp (không phải 'auto')
    if val and val.lower() != "auto":
        return val

    # Tự tìm file mặc định youtube.txt hoặc youtube_music.txt
    is_ytm = app_key in ("ytm", "music")
    default_name = "youtube_music.txt" if is_ytm else "youtube.txt"
    search_paths = [
        default_name,
        os.path.join("..", default_name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", default_name),
    ]

    for p in search_paths:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                ver = f.read().strip()
                if ver:
                    print(f"Đọc phiên bản '{ver}' từ {p}")
                    return ver

    raise FileNotFoundError(
        f"Không tìm thấy phiên bản cho '{app_key}' và không đọc được '{default_name}'."
    )


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def find_release_page(slug: str, version: str) -> str:
    ver_slug = version.replace(".", "-")
    search_urls = [
        f"https://www.apkmirror.com/apk/google-inc/{slug}/{slug}-{ver_slug}-release/",
        f"https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s={urllib.parse.quote(slug + ' ' + version)}",
    ]

    for url in search_urls:
        try:
            html = http_get(url).decode("utf-8", errors="ignore")
            if "/release/" in html:
                m = re.search(
                    r'href="(/apk/google-inc/' + re.escape(slug) + r"/" + re.escape(slug) + r"-" + re.escape(ver_slug) + r'[^"]*release/[^"]*)"',
                    html,
                )
                if m:
                    return "https://www.apkmirror.com" + m.group(1)
                if url.endswith("-release/") and "404" not in html[:1000].lower():
                    return url
        except Exception as exc:
            print(f"Thử tìm release thất bại ({url}): {exc}")

    raise RuntimeError(f"Không tìm thấy trang release APKMirror cho {slug} phiên bản {version}.")


def find_variant_page(release_url: str) -> str:
    html = http_get(release_url).decode("utf-8", errors="ignore")

    # Loại trừ bundle (.apkm / .xapk) và ưu tiên biến thể APK chuẩn
    candidates = re.findall(r'href="(/apk/google-inc/[^"]+-download/)"', html)
    for href in candidates:
        low = href.lower()
        if "bundle" in low or "apkm" in low or "xapk" in low:
            continue
        return "https://www.apkmirror.com" + href

    if candidates:
        return "https://www.apkmirror.com" + candidates[0]

    raise RuntimeError(f"Không tìm thấy trang tải biến thể APK trong {release_url}.")


def find_final_download_url(variant_url: str) -> str:
    html = http_get(variant_url).decode("utf-8", errors="ignore")

    # Tìm link tải trực tiếp từ trang download của APKMirror
    patterns = [
        r'href="(https://www\.apkmirror\.com/wp-content/themes/APKMirror/download\.php\?[^"]+)"',
        r'href="(/wp-content/themes/APKMirror/download\.php\?[^"]+)"',
        r'href="(https://[^"]*download\.php\?id=[^"&]+[^"]*)"',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            link = m.group(1).replace("&amp;", "&")
            if link.startswith("/"):
                link = "https://www.apkmirror.com" + link
            return link

    raise RuntimeError(f"Không tìm thấy liên kết tải trực tiếp từ {variant_url}.")


def verify_apk(file_path: str) -> None:
    if not os.path.isfile(file_path) or os.path.getsize(file_path) < 1024 * 1024:
        raise RuntimeError(f"Tệp '{file_path}' không hợp lệ hoặc quá nhỏ.")
    if not zipfile.is_zipfile(file_path):
        raise RuntimeError(f"Tệp '{file_path}' không phải định dạng APK/ZIP hợp lệ.")


def parse_args():
    parser = argparse.ArgumentParser(description="Tải APK gốc theo phiên bản từ file hoặc tham số.")
    parser.add_argument("app", help="Loại ứng dụng: youtube | ytm")
    parser.add_argument("version_or_file", nargs="?", default="", help="Phiên bản (vd: 21.37.42) hoặc đường dẫn file (vd: ../youtube.txt)")
    parser.add_argument("output", nargs="?", default="", help="Đường dẫn file APK xuất ra")
    return parser.parse_args()


def main():
    args = parse_args()
    app_key = args.app.strip().lower()
    if app_key not in APP_CONFIG:
        print(f"Ứng dụng không được hỗ trợ: {args.app}", file=sys.stderr)
        sys.exit(1)

    cfg = APP_CONFIG[app_key]
    version = resolve_version(app_key, args.version_or_file)
    output_apk = args.output.strip() or (
        "ytm_orig.apk" if app_key in ("ytm", "music") else "yt_orig.apk"
    )

    print(f"Đang tải {cfg['slug']} ({cfg['pkg']}) phiên bản {version} -> {output_apk}")

    release_url = find_release_page(cfg["slug"], version)
    print(f"Release page: {release_url}")

    variant_url = find_variant_page(release_url)
    print(f"Variant page: {variant_url}")

    dl_url = find_final_download_url(variant_url)
    print(f"Download URL: {dl_url}")

    data = http_get(dl_url, timeout=120)
    out_dir = os.path.dirname(output_apk)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_apk, "wb") as f:
        f.write(data)

    verify_apk(output_apk)
    print(f"Hoàn tất tải hợp lệ: {output_apk} ({os.path.getsize(output_apk)} bytes)")


if __name__ == "__main__":
    main()
