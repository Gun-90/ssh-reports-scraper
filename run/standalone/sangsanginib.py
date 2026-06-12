#!/usr/bin/env python3
"""Sangsangin standalone scraper — GitHub Actions 전용.
공통 코어 scrapers/sangsangin_core.py 사용."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.sangsangin_core import scrape_sangsangin

URLS_ENV_KEY = "SANGSANGINIB_URLS_JSON"
FIRM_NM = "상상인증권"

if __name__ == "__main__":
    raw = os.getenv(URLS_ENV_KEY, "")
    if not raw:
        print(f"[{FIRM_NM}] FATAL: {URLS_ENV_KEY} not set", file=sys.stderr)
        sys.exit(1)
    urls = json.loads(raw)
    if not urls:
        print(f"[{FIRM_NM}] FATAL: {URLS_ENV_KEY} is empty", file=sys.stderr)
        sys.exit(1)

    result = scrape_sangsangin(url=urls[0])
    print(f"[{FIRM_NM}] total {len(result)} articles collected", file=sys.stderr)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
