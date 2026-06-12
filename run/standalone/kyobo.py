#!/usr/bin/env python3
"""Kyobo Securities standalone — GA 전용."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrapers.kyobo_core import scrape_kyobo
KEY = "KYOBO_URLS_JSON"
if __name__ == "__main__":
    raw = os.getenv(KEY, "")
    if not raw: print(f"[교보증권] FATAL: {KEY} not set", file=sys.stderr), sys.exit(1)
    result = scrape_kyobo(json.loads(raw))
    print(f"[교보증권] total {len(result)} articles collected", file=sys.stderr)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
