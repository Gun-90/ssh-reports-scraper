#!/usr/bin/env python3
"""Hyundai Motor Securities standalone — GA 전용."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrapers.hmsec_core import scrape_hmsec
KEY = "HMSEC_URLS_JSON"
if __name__ == "__main__":
    raw = os.getenv(KEY, "")
    if not raw: print(f"[현대차증권] FATAL: {KEY} not set", file=sys.stderr), sys.exit(1)
    result = scrape_hmsec(json.loads(raw))
    print(f"[현대차증권] total {len(result)} articles collected", file=sys.stderr)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
