#!/usr/bin/env python3
"""Warn on newly staged hardcoded URLs outside the approved public allowlist."""

import re
import subprocess
import sys
from urllib.parse import urlparse


URL_RE = re.compile(r"https?://[^\s\"'<>`)]+")
ALLOWED_HOST_SUFFIXES = (
    "astral.sh",
    "api.ipify.org",
    "github.com",
    "example.test",
    "localhost",
    "ls-sec.co.kr",
    "msg.ls-sec.co.kr",
    "nls-sec.co.kr",
)
ALLOWED_PATHS = (
    ".github/workflows/",
    "docs/",
    "tests/",
    "tools/",
    "archive/",
)


def staged_added_lines():
    proc = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", "--"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return []

    current_path = ""
    rows = []
    for line in proc.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_path = line.removeprefix("+++ b/")
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        rows.append((current_path, line[1:]))
    return rows


def host_allowed(url):
    host = urlparse(url).hostname or ""
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in ALLOWED_HOST_SUFFIXES)


def path_allowed(path):
    return any(path.startswith(prefix) for prefix in ALLOWED_PATHS)


def main():
    leaks = []
    for path, line in staged_added_lines():
        if path_allowed(path):
            continue
        for url in URL_RE.findall(line):
            if not host_allowed(url):
                leaks.append((path, url))

    if not leaks:
        return 0

    print("Potential hardcoded URL leak detected in staged changes:", file=sys.stderr)
    for path, url in leaks:
        print(f"  {path}: {url}", file=sys.stderr)
    print("Move scraper target URLs to ~/secrets/**/secrets.json urls section.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
