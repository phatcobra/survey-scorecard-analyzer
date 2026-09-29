#!/usr/bin/env python3
"""History-preserving push of a local directory to GitHub via the git data API.

Usage: gh_push_native.py <local_dir> <repo_name> [commit_message]

Unlike scripts/gh_push.py (force-push), this keeps history: it parents the
new commit on the current tip of main. Signs requests natively via the same
credential surrogate as the gh-api wrapper, so large blobs (which exceed the
wrapper's --data arg size limit) work.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    read_response_body,
)

API_BASE = "https://api.github.com"
ALLOWED = ("api.github.com",)
CREDENTIAL = "custom.github"
OWNER = "phatcobra"

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}


def api(method, path, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(API_BASE + path, data=body, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = read_response_body(resp)
            return json.loads(raw.decode("utf-8")) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail}")


def main():
    local_dir, repo = sys.argv[1], sys.argv[2]
    message = sys.argv[3] if len(sys.argv) > 3 else "Update"

    ref = api("GET", f"/repos/{OWNER}/{repo}/git/refs/heads/main")
    parent_sha = ref["object"]["sha"]
    parent_commit = api("GET", f"/repos/{OWNER}/{repo}/git/commits/{parent_sha}")
    base_tree = parent_commit["tree"]["sha"]
    print(f"parent: {parent_sha}")

    entries = []
    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, local_dir)
            with open(full, "rb") as fh:
                content = fh.read()
            try:
                payload = {"content": content.decode("utf-8"),
                           "encoding": "utf-8"}
            except UnicodeDecodeError:
                payload = {"content": base64.b64encode(content).decode(),
                           "encoding": "base64"}
            blob = api("POST", f"/repos/{OWNER}/{repo}/git/blobs", payload)
            entries.append({"path": rel, "mode": "100644", "type": "blob",
                            "sha": blob["sha"]})
    print(f"{len(entries)} blobs")

    tree = api("POST", f"/repos/{OWNER}/{repo}/git/trees",
               {"base_tree": base_tree, "tree": entries})
    commit = api("POST", f"/repos/{OWNER}/{repo}/git/commits",
                 {"message": message, "tree": tree["sha"],
                  "parents": [parent_sha]})
    api("PATCH", f"/repos/{OWNER}/{repo}/git/refs/heads/main",
        {"sha": commit["sha"]})
    print(f"pushed: {commit['sha']}")
    print(f"https://github.com/{OWNER}/{repo}/commit/{commit['sha']}")


if __name__ == "__main__":
    main()
