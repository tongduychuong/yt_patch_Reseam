import argparse
import os
import re
import sys
import urllib.request
import zipfile


# ============================================================
# CONFIG (Dễ chỉnh sửa trực tiếp tại đây)
# ============================================================

YT_PACKAGE = "com.google.android.youtube"
YTM_PACKAGE = "com.google.android.apps.youtube.music"

PATCHES_WEB_URL = "https://reseam.app/vi/patches/"

# Regex dải phiên bản thực tế (hỗ trợ cụm cuối 1-3 chữ số)
YT_VER_RE = re.compile(r"\b(19|[2-9]\d)\.\d{1,3}\.\d{1,3}\b")
YTM_VER_RE = re.compile(r"\b([7-9]|1\d)\.\d{1,3}\.\d{1,3}\b")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
)


# ============================================================
# HELPERS
# ============================================================

def ver_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def extract_near_package(text: str, pkg_name: str, pattern: re.Pattern) -> set[str]:
    found: set[str] = set()
    start = 0
    while True:
        idx = text.find(pkg_name, start)
        if idx == -1:
            break
        chunk = text[max(0, idx - 500) : min(len(text), idx + 5000)]
        for match in pattern.findall(chunk):
            found.add(match)
        start = idx + len(pkg_name)
    return found


def scan_bundle(bundle_path: str) -> tuple[set[str], set[str]]:
    yt_found: set[str] = set()
    ytm_found: set[str] = set()

    if not bundle_path or not os.path.exists(bundle_path):
        print(f"Bundle not found at '{bundle_path}', skipping bundle scan.")
        return yt_found, ytm_found

    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            for name in zf.namelist():
                raw = zf.read(name).decode("utf-8", errors="ignore")
                yt_found.update(extract_near_package(raw, YT_PACKAGE, YT_VER_RE))
                ytm_found.update(extract_near_package(raw, YTM_PACKAGE, YTM_VER_RE))
    except Exception as exc:
        print(f"Zip inspection note: {exc}")

    return yt_found, ytm_found


def scan_web(url: str) -> tuple[set[str], set[str]]:
    yt_found: set[str] = set()
    ytm_found: set[str] = set()

    try:
        html = fetch_text(url)
        yt_found.update(extract_near_package(html, YT_PACKAGE, YT_VER_RE))
        ytm_found.update(extract_near_package(html, YTM_PACKAGE, YTM_VER_RE))

        js_paths = set(re.findall(r"""["']([^"']*\.js[^"']*)["']""", html))
        for path in list(js_paths)[:20]:
            if path.startswith("/"):
                js_url = "https://reseam.app" + path
            elif path.startswith("http"):
                js_url = path
            else:
                js_url = url.rstrip("/") + "/" + path.lstrip("/")
            try:
                js_text = fetch_text(js_url)
                yt_found.update(extract_near_package(js_text, YT_PACKAGE, YT_VER_RE))
                ytm_found.update(extract_near_package(js_text, YTM_PACKAGE, YTM_VER_RE))
            except Exception:
                continue
    except Exception as exc:
        print(f"Web fetch note: {exc}")

    return yt_found, ytm_found


# ============================================================
# MAIN
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Resolve latest YT and YTM versions.")
    parser.add_argument("--bundle", default="patches.reseam", help="Path to patches.reseam")
    parser.add_argument("--yt-version", default=os.environ.get("INPUT_YT_VER", ""), help="Override YT version")
    parser.add_argument("--ytm-version", default=os.environ.get("INPUT_YTM_VER", ""), help="Override YTM version")
    parser.add_argument("--env-file", default="", help="Optional path to write YT_VER=... and YTM_VER=...")
    return parser.parse_args()


def main():
    args = parse_args()
    yt_ver = args.yt_version.strip()
    ytm_ver = args.ytm_version.strip()

    yt_candidates: set[str] = set()
    ytm_candidates: set[str] = set()

    if not yt_ver or not ytm_ver:
        b_yt, b_ytm = scan_bundle(args.bundle)
        yt_candidates.update(b_yt)
        ytm_candidates.update(b_ytm)

    if (not yt_ver and not yt_candidates) or (not ytm_ver and not ytm_candidates):
        w_yt, w_ytm = scan_web(PATCHES_WEB_URL)
        if not yt_ver:
            yt_candidates.update(w_yt)
        if not ytm_ver:
            ytm_candidates.update(w_ytm)

    yt_sorted = sorted(yt_candidates, key=ver_tuple)
    ytm_sorted = sorted(ytm_candidates, key=ver_tuple)

    print("All matched YT versions:", yt_sorted)
    print("All matched YTM versions:", ytm_sorted)

    if not yt_ver:
        if not yt_sorted:
            print("ERROR: Could not resolve any YouTube version.")
            sys.exit(1)
        yt_ver = yt_sorted[-1]

    if not ytm_ver:
        if not ytm_sorted:
            print("ERROR: Could not resolve any YouTube Music version.")
            sys.exit(1)
        ytm_ver = ytm_sorted[-1]

    print(f"Resolved YouTube version: {yt_ver}")
    print(f"Resolved YouTube Music version: {ytm_ver}")

    if args.env_file:
        with open(args.env_file, "w", encoding="utf-8") as f:
            f.write(f"YT_VER={yt_ver}\n")
            f.write(f"YTM_VER={ytm_ver}\n")


if __name__ == "__main__":
    main()
