import json
import os
import re
import urllib.error
import urllib.request


def gh_get_json(url: str, token: str = ""):
    headers = {
        "User-Agent": "github-actions-reseam-checker",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_repo_tag(target_repo: str, token: str = "") -> str:
    # 1. Thử /releases/latest
    try:
        data = gh_get_json(f"https://api.github.com/repos/{target_repo}/releases/latest", token)
        if isinstance(data, dict):
            tag = (data.get("tag_name") or "").strip()
            if tag:
                return tag
    except urllib.error.HTTPError as e:
        print(f"[{target_repo}] /releases/latest -> HTTP {e.code}")

    # 2. Fallback /releases (lấy release đầu tiên, kể cả prerelease)
    try:
        releases = gh_get_json(f"https://api.github.com/repos/{target_repo}/releases?per_page=5", token)
        if isinstance(releases, list) and releases:
            tag = (releases[0].get("tag_name") or "").strip()
            if tag:
                return tag
    except urllib.error.HTTPError as e:
        print(f"[{target_repo}] /releases -> HTTP {e.code}")

    # 3. Fallback /tags (lấy tag mới nhất nếu repo không tạo Release)
    try:
        tags = gh_get_json(f"https://api.github.com/repos/{target_repo}/tags?per_page=5", token)
        if isinstance(tags, list) and tags:
            tag = (tags[0].get("name") or "").strip()
            if tag:
                return tag
    except urllib.error.HTTPError as e:
        print(f"[{target_repo}] /tags -> HTTP {e.code}")

    raise RuntimeError(f"Không tìm thấy release hoặc tag nào cho {target_repo}")


def extract_tag_for_keyword(keyword: str, text: str) -> str:
    for line in text.splitlines():
        if keyword.lower() in line.lower() and ":" in line:
            after_colon = line.split(":", 1)[1].strip()
            m_link = re.search(
                r"\[([vV]?\d+\.\d+(?:\.\d+)?(?:-[A-Za-z0-9._-]+)?)\]\([^)]+\)",
                after_colon,
            )
            if m_link:
                return m_link.group(1).strip()
            m = re.search(r"([vV]?\d+\.\d+(?:\.\d+)?(?:-[A-Za-z0-9._-]+)?)", after_colon)
            if m:
                return m.group(1).strip()
            cleaned = after_colon.strip("*` ").split()[0] if after_colon.strip("*` ") else ""
            if cleaned:
                return cleaned.strip("*`")
    return ""


def main() -> None:
    token = os.environ.get("GH_TOKEN", "").strip()
    repo = os.environ["GH_REPO"].strip()
    force = os.environ.get("FORCE_BUILD", "false").strip().lower() == "true"

    latest_cli = resolve_repo_tag("Reseam/reseam", token)
    latest_patches = resolve_repo_tag("Reseam/patches", token)

    prev_cli = ""
    prev_patches = ""

    try:
        rel = gh_get_json(f"https://api.github.com/repos/{repo}/releases/latest", token)
        body = (rel.get("body") or "") if isinstance(rel, dict) else ""

        prev_cli = extract_tag_for_keyword("Reseam/reseam", body)
        prev_patches = extract_tag_for_keyword("Reseam/patches", body)

        if not prev_cli or not prev_patches:
            print("DEBUG release body:")
            print(body)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("No previous release found yet; proceeding to build.")
        else:
            raise

    changed = (latest_cli != prev_cli) or (latest_patches != prev_patches)
    should_build = changed or force

    cli_link_tag = f"[{latest_cli}](https://github.com/Reseam/reseam/releases/tag/{latest_cli})"
    patches_link_tag = f"[{latest_patches}](https://github.com/Reseam/patches/releases/tag/{latest_patches})"

    print(f"Latest release CLI:     {prev_cli or '(none)'} -> Current: {latest_cli}")
    print(f"Latest release Patches: {prev_patches or '(none)'} -> Current: {latest_patches}")
    print(f"Changed: {changed} | Force: {force} | Should build: {should_build}")

    github_output = os.environ.get("GITHUB_OUTPUT", "").strip()
    if github_output:
        with open(github_output, "a", encoding="utf-8") as out:
            out.write(f"should_build={'true' if should_build else 'false'}\n")
            out.write(f"cli_tag={cli_link_tag}\n")
            out.write(f"patches_tag={patches_link_tag}\n")


if __name__ == "__main__":
    main()
