#!/usr/bin/env python3
"""
고속 동기식 Backfill — tags/sector/stock_names 일괄 채우기

asyncio 오버헤드 없는 순수 동기 처리로 초당 수천 건 처리 가능.
Production 서버에서 직접 실행하거나 scheduler에서 유휴시간에 호출.

사용법:
    uv run enricher/backfill_sync.py [batch_size] [max_batches]

    batch_size: 한 배치당 처리할 row 수 (기본값: 5000)
    max_batches: 최대 배치 수 (기본값: 0 = 전부 처리)
"""

import json
import os
import sys
import time
from datetime import datetime

# standalone 실행 시 프로젝트 루트를 path에 추가
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from enricher.tag_extractor import TagExtractionManager


def get_conn():
    load_dotenv(override=False)
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_REPORT_DB", "ssh_reports_hub"),
        user=os.getenv("POSTGRES_ENRICH_USER", os.getenv("POSTGRES_USER", "ssh_reports_hub")),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def run_backfill(batch_size: int = 5000, max_batches: int = 0):
    conn = get_conn()
    extractor = TagExtractionManager()

    # 전체 미처리 건수 확인
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM tbl_sec_reports
            WHERE (tags IS NULL OR tags = '[]'::jsonb OR tags = '[]')
              AND article_title IS NOT NULL AND article_title != ''
        """)
        total_pending = cur.fetchone()[0]

    print(f"[backfill] 총 미처리: {total_pending:,}건 | 배치={batch_size:,} | 최대배치={'무제한' if max_batches==0 else max_batches}")
    print()

    batch_num = 0
    total_processed = 0
    total_enriched = 0
    start_time = time.time()

    while True:
        if max_batches > 0 and batch_num >= max_batches:
            break

        batch_num += 1
        batch_start = time.time()

        # 배치 조회
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT report_id, firm_nm, article_title
                FROM tbl_sec_reports
                WHERE (tags IS NULL OR tags = '[]'::jsonb OR tags = '[]')
                  AND article_title IS NOT NULL AND article_title != ''
                ORDER BY report_id
                LIMIT %s
            """, (batch_size,))
            rows = [dict(r) for r in cur.fetchall()]

        if not rows:
            print(f"[backfill] ✅ 더 이상 처리할 레포트가 없습니다.")
            break

        batch_count = len(rows)
        enriched_in_batch = 0

        # 동기식 추출 + UPDATE (대량 커밋)
        with conn.cursor() as cur:
            for row in rows:
                result = extractor.extract_tags_sync(
                    row["article_title"],
                    row.get("firm_nm", ""),
                )
                tags_json = json.dumps(result["tags"], ensure_ascii=False)
                stocks_json = json.dumps(result["stock_names"], ensure_ascii=False)
                sector_val = result["sector"] or ""

                cur.execute("""
                    UPDATE tbl_sec_reports
                    SET tags = %s, stock_names = %s, sector = %s
                    WHERE report_id = %s
                """, (tags_json, stocks_json, sector_val, row["report_id"]))

                if result["tags"] or result["stock_names"] or result["sector"]:
                    enriched_in_batch += 1

        conn.commit()

        total_processed += batch_count
        total_enriched += enriched_in_batch

        batch_elapsed = time.time() - batch_start
        total_elapsed = time.time() - start_time
        rate = total_processed / total_elapsed if total_elapsed > 0 else 0
        remaining = total_pending - total_processed
        eta_sec = remaining / rate if rate > 0 else 0

        print(
            f"  📦 배치 #{batch_num}: {batch_count:,}건 처리 "
            f"({enriched_in_batch:,}건 태그추출) | "
            f"{batch_elapsed:.1f}초 ({batch_count/batch_elapsed:.0f}건/초) | "
            f"누계: {total_processed:,}/{total_pending:,} ({rate:.0f}건/초) | "
            f"ETA: {eta_sec/60:.0f}분"
        )

    conn.close()

    total_elapsed = time.time() - start_time
    print()
    print(f"[backfill] 🏁 완료! 총 {total_processed:,}건 처리, {total_enriched:,}건 enrichment")
    print(f"[backfill] ⏱️  소요: {total_elapsed:.1f}초 ({total_elapsed/60:.1f}분)")
    print(f"[backfill] ⚡ 평균: {total_processed/total_elapsed:.0f}건/초")

    return total_processed


if __name__ == "__main__":
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    max_batches = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    run_backfill(batch_size, max_batches)
