#!/usr/bin/env python3
"""TOSSinvest standalone — GA 전용. scrapers/toss_core.py 사용."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrapers.toss_core import scrape_toss

FIRM_NM, KEY = "토스증권", "TOSS_URLS_JSON"

if __name__ == "__main__":
    raw = os.getenv(KEY, "")
    if not raw: print(f"[{FIRM_NM}] FATAL: {KEY} not set", file=sys.stderr), sys.exit(1)
    urls = json.loads(raw)
    if not urls: print(f"[{FIRM_NM}] FATAL: empty", file=sys.stderr), sys.exit(1)
    result = scrape_toss(urls)
    print(f"[{FIRM_NM}] total {len(result)} articles collected", file=sys.stderr)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
