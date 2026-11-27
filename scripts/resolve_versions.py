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

# Bắt buộc đủ 3 cụm X.Y.Z (ví dụ: 21.37.42, 20.26.46, 21.23.492)
FULL_VER_RE = re.compile(r"\b(\d{1,2})\.(\d{1,3})\.(\d{1,3})\b")

# Giới hạn dải major hợp lệ cho từng app
YT_MAJOR_MIN, YT_MAJOR_MAX = 19, 30
YTM_MAJOR_MIN, YTM_MAJOR_MAX = 7, 15

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
)


# ============================================================
# HELPERS
# ============================================================

def is_valid_full_version(ver: str, major_min: int, major_max: int) -> bool:
    parts = ver.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return False
    major = int(parts[0])
    return major_min <= major <= major_max


def ver_tuple(version: str) -> tuple[int, int, int]:
    a, b, c = version.split(".")
    return (int(a), int(b), int(c))


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


def extract_full_versions_near_package(
    text: str, pkg_name: str, major_min: int, major_max: int
) -> set[str]:
    found: set[str] = set()
    start = 0
    while True:
        idx = text.find(pkg_name, start)
        if idx == -1:
            break
        chunk = text[max(0, idx - 500) : min(len(text), idx + 8000)]
        for major_s, minor_s, patch_s in FULL_VER_RE.findall(chunk):
            candidate = f"{int(major_s)}.{int(minor_s)}.{int(patch_s)}"
            if is_valid_full_version(candidate, major_min, major_max):
                found.add(candidate)
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
                yt_found.update(
                    extract_full_versions_near_package(
                        raw, YT_PACKAGE, YT_MAJOR_MIN, YT_MAJOR_MAX
                    )
                )
                ytm_found.update(
                    extract_full_versions_near_package(
                        raw, YTM_PACKAGE, YTM_MAJOR_MIN, YTM_MAJOR_MAX
                    )
                )
    except Exception as exc:
        print(f"Zip inspection note: {exc}")

    return yt_found, ytm_found


def scan_web(url: str) -> tuple[set[str], set[str]]:
    yt_found: set[str] = set()
    ytm_found: set[str] = set()

    try:
        html = fetch_text(url)
        yt_found.update(
            extract_full_versions_near_package(
                html, YT_PACKAGE, YT_MAJOR_MIN, YT_MAJOR_MAX
            )
        )
        ytm_found.update(
            extract_full_versions_near_package(
                html, YTM_PACKAGE, YTM_MAJOR_MIN, YTM_MAJOR_MAX
            )
        )

        js_paths = set(re.findall(r"""["']([^"']*\.js[^"']*)["']""", html))
        for path in list(js_paths)[:25]:
            if path.startswith("/"):
                js_url = "https://reseam.app" + path
            elif path.startswith("http"):
                js_url = path
            else:
                js_url = url.rstrip("/") + "/" + path.lstrip("/")
            try:
                js_text = fetch_text(js_url)
                yt_found.update(
                    extract_full_versions_near_package(
                        js_text, YT_PACKAGE, YT_MAJOR_MIN, YT_MAJOR_MAX
                    )
                )
                ytm_found.update(
                    extract_full_versions_near_package(
                        js_text, YTM_PACKAGE, YTM_MAJOR_MIN, YTM_MAJOR_MAX
                    )
                )
            except Exception:
                continue
    except Exception as exc:
        print(f"Web fetch note: {exc}")

    return yt_found, ytm_found


def write_version_file(path: str, version: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{version}\n")


# ============================================================
# MAIN
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Resolve full YT and YTM versions.")
    parser.add_argument("--bundle", default="patches.reseam", help="Path to patches.reseam")
    parser.add_argument("--yt-version", default=os.environ.get("INPUT_YT_VER", ""), help="Override YT version")
    parser.add_argument("--ytm-version", default=os.environ.get("INPUT_YTM_VER", ""), help="Override YTM version")
    parser.add_argument("--yt-out", default="youtube.txt", help="Output file path for YT version")
    parser.add_argument("--ytm-out", default="youtube_music.txt", help="Output file path for YTM version")
    parser.add_argument("--env-file", default="", help="Optional path to write YT_VER=... and YTM_VER=...")
    return parser.parse_args()


def main():
    args = parse_args()
    yt_ver = args.yt_version.strip()
    ytm_ver = args.ytm_version.strip()

    if yt_ver and not is_valid_full_version(yt_ver, 1, 99):
        print(f"ERROR: Provided YT version '{yt_ver}' is not full X.Y.Z format.")
        sys.exit(1)
    if ytm_ver and not is_valid_full_version(ytm_ver, 1, 99):
        print(f"ERROR: Provided YTM version '{ytm_ver}' is not full X.Y.Z format.")
        sys.exit(1)

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

    print("All matched full YT versions:", yt_sorted)
    print("All matched full YTM versions:", ytm_sorted)

    if not yt_ver:
        if not yt_sorted:
            print("ERROR: Could not resolve any full YouTube version (X.Y.Z).")
            sys.exit(1)
        yt_ver = yt_sorted[-1]

    if not ytm_ver:
        if not ytm_sorted:
            print("ERROR: Could not resolve any full YouTube Music version (X.Y.Z).")
            sys.exit(1)
        ytm_ver = ytm_sorted[-1]

    print(f"Resolved YouTube version: {yt_ver}")
    print(f"Resolved YouTube Music version: {ytm_ver}")

    write_version_file(args.yt_out, yt_ver)
    write_version_file(args.ytm_out, ytm_ver)

    if args.env_file:
        with open(args.env_file, "w", encoding="utf-8") as f:
            f.write(f"YT_VER={yt_ver}\n")
            f.write(f"YTM_VER={ytm_ver}\n")


if __name__ == "__main__":
    main()
