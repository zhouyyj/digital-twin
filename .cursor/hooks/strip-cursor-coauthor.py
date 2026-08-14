#!/usr/bin/env python3
"""Drop Cursor co-author trailers so cursoragent never lands on GitHub."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

TRAILER = re.compile(
    r"^Co-authored-by:.*(?:Cursor|cursoragent@cursor\.com).*\n?",
    re.IGNORECASE | re.MULTILINE,
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True)


def clean_message(msg: str) -> str:
    cleaned = TRAILER.sub("", msg)
    if cleaned == msg:
        return msg
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.rstrip() + "\n"


def rewrite_message_file(path: str) -> None:
    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    cleaned = clean_message(original)
    if cleaned != original:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(cleaned)


def rewrite_head() -> None:
    try:
        original = git("log", "-1", "--format=%B")
    except subprocess.CalledProcessError:
        return
    cleaned = clean_message(original)
    if cleaned == original:
        return

    tree = git("rev-parse", "HEAD^{tree}").strip()
    parent_line = git("rev-list", "--parents", "-n", "1", "HEAD").split()
    parents = parent_line[1:]
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = git("log", "-1", "--format=%an").rstrip("\n")
    env["GIT_AUTHOR_EMAIL"] = git("log", "-1", "--format=%ae").rstrip("\n")
    env["GIT_AUTHOR_DATE"] = git("log", "-1", "--format=%aD").rstrip("\n")
    env["GIT_COMMITTER_NAME"] = git("log", "-1", "--format=%cn").rstrip("\n")
    env["GIT_COMMITTER_EMAIL"] = git("log", "-1", "--format=%ce").rstrip("\n")
    env["GIT_COMMITTER_DATE"] = git("log", "-1", "--format=%cD").rstrip("\n")

    cmd = ["git", "commit-tree", tree]
    for parent in parents:
        cmd.extend(["-p", parent])
    new = subprocess.check_output(cmd, input=cleaned, text=True, env=env).strip()
    subprocess.check_call(["git", "reset", "--soft", new])


def command_looks_like_commit(command: str) -> bool:
    return bool(re.search(r"\bgit\s+(?:-C\s+\S+\s+)*commit\b", command))


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--message-file"] and len(args) >= 2:
        rewrite_message_file(args[1])
        return 0
    if args[:1] == ["--head"]:
        rewrite_head()
        return 0

    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    command = ""
    if raw.strip().startswith("{"):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            command = str(payload.get("command") or payload.get("cmd") or "")
    if command and not command_looks_like_commit(command):
        return 0
    if command or not raw.strip():
        rewrite_head()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
