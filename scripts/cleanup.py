import json
import os
import urllib.error
import urllib.request


def gh_req(method: str, url: str, headers: dict, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def cleanup_workflow_runs(repo: str, headers: dict, current_run_id: int, keep_count: int = 5) -> None:
    runs_data = gh_req("GET", f"https://api.github.com/repos/{repo}/actions/runs?per_page=100", headers)
    runs = (runs_data or {}).get("workflow_runs", [])
    runs.sort(key=lambda r: r.get("id", 0), reverse=True)

    keep_run_ids = {r.get("id") for r in runs[:keep_count]}
    keep_run_ids.add(current_run_id)

    for r in runs:
        rid = r.get("id")
        if rid and rid not in keep_run_ids:
            try:
                gh_req("DELETE", f"https://api.github.com/repos/{repo}/actions/runs/{rid}", headers)
                print(f"Deleted old workflow run: {rid}")
            except urllib.error.HTTPError as e:
                print(f"Skip run {rid} (HTTP {e.code})")


def cleanup_releases_and_tags(repo: str, headers: dict, keep_count: int = 1) -> None:
    releases = gh_req("GET", f"https://api.github.com/repos/{repo}/releases?per_page=100", headers) or []
    releases.sort(
        key=lambda rel: (rel.get("published_at") or "", rel.get("id") or 0),
        reverse=True,
    )

    kept_releases = releases[:keep_count]
    kept_tags = {
        (rel.get("tag_name") or "").strip()
        for rel in kept_releases
        if (rel.get("tag_name") or "").strip()
    }
    print(f"Keeping latest release(s): {', '.join(sorted(kept_tags)) or '(none)'}")

    for rel in releases[keep_count:]:
        rel_id = rel.get("id")
        tag_name = (rel.get("tag_name") or "").strip()
        if rel_id:
            try:
                gh_req("DELETE", f"https://api.github.com/repos/{repo}/releases/{rel_id}", headers)
                print(f"Deleted old release: {tag_name or rel_id}")
            except urllib.error.HTTPError as e:
                print(f"Failed to delete release {rel_id}: HTTP {e.code}")

        if tag_name and tag_name not in kept_tags:
            try:
                gh_req("DELETE", f"https://api.github.com/repos/{repo}/git/refs/tags/{tag_name}", headers)
                print(f"Deleted old git tag: {tag_name}")
            except urllib.error.HTTPError as e:
                print(f"Skip deleting tag {tag_name} (HTTP {e.code})")


def main() -> None:
    repo = os.environ["GH_REPO"].strip()
    token = os.environ["GH_TOKEN"].strip()
    current_run_id = int(os.environ["CURRENT_RUN_ID"])
    keep_runs = int(os.environ.get("KEEP_RUNS", "5"))
    keep_releases = int(os.environ.get("KEEP_RELEASES", "1"))

    headers = {
        "User-Agent": "github-actions-cleanup",
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }

    cleanup_workflow_runs(repo, headers, current_run_id, keep_count=keep_runs)
    cleanup_releases_and_tags(repo, headers, keep_count=keep_releases)


if __name__ == "__main__":
    main()
