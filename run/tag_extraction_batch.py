"""
Tag Extraction Batch - 레포트 제목에서 태그/종목명/산업 추출 배치 작업

gemini_summary_batch.py와 동일한 워크플로우:
1. 태그가 없는 레포트 목록 조회
2. 제목을 Gemini Text API로 분석 → JSON 추출
3. PostgreSQL에 결과 저장

사용법:
  python run/tag_extraction_batch.py [batch_limit]

  batch_limit: 한 번에 처리할 레포트 수 (기본값: 20)
               제목만 전송하므로 토큰 사용량이 매우 적어 더 큰 배치 가능
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.db_factory import get_db
from enricher import TagExtractionManager


async def run_batch_tag_extraction(batch_limit=20):
    print(f"🏷️  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 태그 추출 배치 작업 시작...")
    print(f"   배치 크기: {batch_limit}")

    db = get_db()
    tag_manager = TagExtractionManager()

    # ── 1) 태그 없는 레포트 조회 ──
    pending_reports = await db.fetch_pending_tag_reports(limit=batch_limit)

    if not pending_reports:
        print("✅ 모든 레포트에 태그가 이미 존재합니다. 작업을 종료합니다.")
        return

    total = len(pending_reports)
    print(f"📋 총 {total}개 레포트의 태그를 추출합니다.\n")

    success_count = 0
    fail_count = 0
    processed = 0

    for report in pending_reports:
        processed += 1
        report_id = report["report_id"]
        title = report.get("article_title", "")
        firm_nm = report.get("firm_nm", "")

        if not title.strip():
            print(f"  [{processed}/{total}] ⏭️  report_id={report_id}: 제목 없음, 스킵")
            continue

        print(f"  [{processed}/{total}] 🔍 report_id={report_id}: {title[:80]}...")

        try:
            # ── 2) Gemini로 태그 추출 ──
            result = await tag_manager.extract_tags(
                article_title=title,
                firm_nm=firm_nm,
                report_id=report_id,
            )

            if result.get("status") != "success":
                print(f"    ❌ 추출 실패: {result.get('error', 'Unknown error')}")
                fail_count += 1
                continue

            tags = result.get("tags", [])
            stock_names = result.get("stock_names", [])
            sector = result.get("sector", "")
            action = result.get("action_type", "")

            # action_type이 있으면 tags에 추가
            if action and action not in tags:
                tags = [action] + tags

            # ── 3) DB 저장 ──
            await db.update_report_tags(report_id, tags, stock_names, sector)

            print(f"    ✅ 태그={tags}, 종목={stock_names}, 섹터={sector}")
            success_count += 1

            # ── 4) API rate limit 방지 대기 ──
            # 제목 only 요청은 토큰이 적어 rate limit 여유 있음
            await asyncio.sleep(1.0)

        except Exception as e:
            print(f"    🔥 예외 발생: {e}")
            fail_count += 1

    # ── 결과 출력 ──
    print(f"\n📊 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 태그 추출 완료")
    print(f"   총 {total}개 중 성공: {success_count}, 실패: {fail_count}")

    # 남은 미처리 건수 확인
    remaining = await db.fetch_pending_tag_reports(limit=1)
    remaining_count = "다수" if remaining else "0"
    if remaining:
        # 대략적인 카운트를 위해 fetch
        pass
    print(f"   ⏳ 미처리 레포트가 {'있습니다' if remaining else '없습니다'}. 필요시 다시 실행하세요.")


if __name__ == "__main__":
    load_dotenv()

    # 실행 인자로 batch_limit 받기
    limit = 20
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            limit = 20

    asyncio.run(run_batch_tag_extraction(batch_limit=limit))
