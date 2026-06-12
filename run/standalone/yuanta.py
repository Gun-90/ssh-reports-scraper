#!/usr/bin/env python3
"""Yuanta Securities standalone — GA 전용."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrapers.yuanta_core import scrape_yuanta
KEY = "YUANTA_URLS_JSON"
if __name__ == "__main__":
    raw = os.getenv(KEY, "")
    if not raw: print(f"[유안타증권] FATAL: {KEY} not set", file=sys.stderr), sys.exit(1)
    cfg = json.loads(raw)
    result = scrape_yuanta(base_url=cfg["base_url"])
    print(f"[유안타증권] total {len(result)} articles collected", file=sys.stderr)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
