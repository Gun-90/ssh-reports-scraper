#!/usr/bin/env python3
"""IBK Securities standalone — GA 전용."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrapers.ibk_core import scrape_ibk

KEY = "IBK_URLS_JSON"
BOARDS = [
    {"name":"전략/시황","screen":"IKO010101","path":"invreport"},
    {"name":"기업분석","screen":"IKO010201","path":"busreport"},
    {"name":"산업분석","screen":"IKO010301","path":"indreport"},
    {"name":"경제/채권","screen":"IKO010401","path":"comment"},
    {"name":"해외기업분석","screen":"IKO010501","path":"overseasreport","menu_tp":"0"},
    {"name":"글로벌ETF","screen":"IKO010501","path":"overseasreport","menu_tp":"1"},
]

if __name__ == "__main__":
    raw = os.getenv(KEY, "")
    if not raw: print(f"[IBK투자증권] FATAL: {KEY} not set", file=sys.stderr), sys.exit(1)
    urls = json.loads(raw)
    if not urls or len(urls) < 6: print(f"[IBK투자증권] FATAL: need 6 URLs", file=sys.stderr), sys.exit(1)
    boards = [{**b, "url": urls[i]} for i, b in enumerate(BOARDS)]
    result = scrape_ibk(boards)
    print(f"[IBK투자증권] total {len(result)} articles collected", file=sys.stderr)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
