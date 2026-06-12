#!/usr/bin/env python3
"""DB Financial Investment standalone — GA 전용. scrapers/dbfi_core.py 사용."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrapers.dbfi_core import scrape_dbfi

FIRM_NM, KEY = "DB증권", "DBFI_URLS_JSON"

if __name__ == "__main__":
    raw = os.getenv(KEY, "")
    if not raw: print(f"[{FIRM_NM}] FATAL: {KEY} not set", file=sys.stderr), sys.exit(1)
    cfg = json.loads(raw)
    if not cfg.get("url_paths"): print(f"[{FIRM_NM}] FATAL: url_paths empty", file=sys.stderr), sys.exit(1)
    result = scrape_dbfi(cfg)
    print(f"[{FIRM_NM}] total {len(result)} articles collected", file=sys.stderr)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
