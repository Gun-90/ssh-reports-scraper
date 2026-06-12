#!/usr/bin/env python3
import json,os,sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrapers.sks_core import scrape_sks
K="SKS_URLS_JSON"
if __name__=="__main__":
    raw=os.getenv(K,"")
    if not raw:print(f"[SK증권] FATAL: {K} not set",file=sys.stderr),sys.exit(1)
    result=scrape_sks(json.loads(raw))
    print(f"[SK증권] total {len(result)} articles collected",file=sys.stderr)
    json.dump(result,sys.stdout,ensure_ascii=False,indent=2)
