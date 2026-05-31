#!/bin/bash
# ============================================================
# Emergency Scrape All — GitHub Actions 장애시 서버 직접 스크래핑
# ============================================================
# 사용법:
#   bash scripts/emergency_scrape_all.sh
#
# 또는 개별 증권사만:
#   EMERGENCY_FIRMS="HANA_3,KBsec_4" bash scripts/emergency_scrape_all.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

FIRMS="${EMERGENCY_FIRMS:-}"

echo "============================================"
echo " EMERGENCY SCRAPE — 서버 직접 스크래핑"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

# 1. Standalone 스크래퍼 실행 → JSON 저장
TMPFILE=$(mktemp /tmp/emergency_scrape_XXXXXX.json)
trap "rm -f $TMPFILE" EXIT

FIRMS_ARG=""
if [ -n "$FIRMS" ]; then
    FIRMS_ARG="--firms $FIRMS"
    echo "[1/2] 특정 증권사 스크래핑: $FIRMS"
else
    echo "[1/2] 전체 증권사 스크래핑 (LS 제외)"
fi

uv run python scripts/standalone_all_scraper.py $FIRMS_ARG --timeout 120 > "$TMPFILE" 2>/tmp/emergency_scrape.log

COUNT=$(python3 -c "import json; d=json.load(open('$TMPFILE')); print(d.get('total_articles', 0))")
echo "      → $COUNT articles scraped"
echo ""

# 2. DB import
echo "[2/2] DB import..."
uv run python scripts/import_all_artifact.py --json-file "$TMPFILE"

echo ""
echo "============================================"
echo " EMERGENCY SCRAPE COMPLETE"
echo "============================================"
