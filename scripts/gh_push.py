#!/usr/bin/env python3
"""Push a local directory to a new GitHub repo via the git data API.

Usage: gh_push.py <local_dir> <repo_name> [commit_message]
Creates the repo (public), seeds it (empty repos reject blob creation),
then builds blobs -> trees -> commit -> updates main.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys

GH = os.path.expanduser("~/workspace/skills/github/bin/gh-api")
OWNER = "phatcobra"


def api(method, path, data=None):
    cmd = [GH, "--method", method]
    if data is not None:
        cmd += ["--data", json.dumps(data)]
    cmd.append(path)
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"gh-api {method} {path} failed: {out.stderr}\n{out.stdout}")
    return json.loads(out.stdout) if out.stdout.strip() else {}


def main():
    local_dir, repo = sys.argv[1], sys.argv[2]
    message = sys.argv[3] if len(sys.argv) > 3 else "Initial commit"

    # 1. create repo (ignore if it already exists)
    try:
        api("POST", "/user/repos",
            {"name": repo, "private": False,
             "description": "Survey/scorecard interpretation analyzer: cross-checks a branch scorecard's binary pass/fail interpretation of 1-10 customer ratings against written-feedback evidence."})
        print("repo created")
    except RuntimeError as e:
        if "already exists" in str(e) or "422" in str(e):
            print("repo exists, continuing")
        else:
            raise

    # 2. seed via contents API (empty repos reject git-database blob creation)
    api("PUT", f"/repos/{OWNER}/{repo}/contents/.gitkeep",
        {"message": "seed", "content": base64.b64encode(b"").decode()})
    print("seeded")

    # 3. create blobs for every file
    entries = []
    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__")]
        for f in files:
            if f == ".gitkeep":
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, local_dir)
            with open(full, "rb") as fh:
                content = fh.read()
            try:
                text = content.decode("utf-8")
                blob = api("POST", f"/repos/{OWNER}/{repo}/git/blobs",
                           {"content": text, "encoding": "utf-8"})
            except UnicodeDecodeError:
                blob = api("POST", f"/repos/{OWNER}/{repo}/git/blobs",
                           {"content": base64.b64encode(content).decode(), "encoding": "base64"})
            entries.append({"path": rel, "mode": "100644", "type": "blob",
                            "sha": blob["sha"]})
    print(f"{len(entries)} blobs")

    # 4. tree + commit (drop the seed file by not including it)
    tree = api("POST", f"/repos/{OWNER}/{repo}/git/trees",
               {"tree": entries})
    commit = api("POST", f"/repos/{OWNER}/{repo}/git/commits",
                 {"message": message, "tree": tree["sha"]})
    api("PATCH", f"/repos/{OWNER}/{repo}/git/refs/heads/main",
        {"sha": commit["sha"], "force": True})
    print(f"pushed: {commit['sha']}")
    print(f"https://github.com/{OWNER}/{repo}")


if __name__ == "__main__":
    main()
