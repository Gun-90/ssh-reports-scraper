#!/usr/bin/env python3
"""Shinyoung Securities standalone — GA 전용. Config는 Secret에서 JSON으로 주입."""
import json,os,sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrapers.shinyoung_core import scrape_shinyoung
K="SHINYOUNG_URLS_JSON"
if __name__=="__main__":
    raw=os.getenv(K,"")
    if not raw:print(f"[신영증권] FATAL: {K} not set",file=sys.stderr),sys.exit(1)
    cfg=json.loads(raw)
    result=scrape_shinyoung(cfg)
    print(f"[신영증권] total {len(result)} articles collected",file=sys.stderr)
    json.dump(result,sys.stdout,ensure_ascii=False,indent=2)
