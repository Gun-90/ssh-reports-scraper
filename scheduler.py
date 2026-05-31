# -*- coding:utf-8 -*- 
import os
import subprocess
import sys
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

# 공통 로그 설정 적용
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from utils.logger_util import setup_logger
setup_logger("scheduler")

def run_scraper():
    """메인 스크래퍼 실행 (scraper.py) — enrich + send (스크래핑은 GitHub Actions로 전환)"""
    logger.info("--- [Job Start] Main Scraper (enrich + send) ---")
    try:
        result = subprocess.run(
            ["uv", "run", "scraper.py"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            logger.error(f"Scraper process exited with error code {result.returncode}")
            if result.stderr:
                logger.error(f"Scraper Error Output:\n{result.stderr}")
        else:
            logger.success("Scraper job completed successfully.")
    except Exception as e:
        logger.error(f"Execution Error: {e}")
    logger.info("--- [Job End] Main Scraper ---")


def run_import_ls():
    """LS 증권사 GitHub Actions 아티팩트 → DB import"""
    logger.info("--- [Job Start] LS Artifact Import ---")
    try:
        result = subprocess.run(
            ["uv", "run", "python", "scripts/import_ls_artifact.py"],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        if result.returncode != 0:
            logger.error(f"LS import exited with code {result.returncode}")
            if result.stderr:
                logger.error(f"LS import stderr:\n{result.stderr[:500]}")
        else:
            # 요약만 출력
            for line in result.stdout.strip().split('\n'):
                if any(kw in line for kw in ('Import', 'skipped', 'inserted', 'Complete')):
                    logger.info(f"[LS-import] {line.strip()}")
    except subprocess.TimeoutExpired:
        logger.error("LS import timed out (300s)")
    except Exception as e:
        logger.error(f"LS import error: {e}")
    logger.info("--- [Job End] LS Artifact Import ---")


def run_import_all():
    """전체 증권사 GitHub Actions 아티팩트 → DB import"""
    logger.info("--- [Job Start] All-Firms Artifact Import ---")
    try:
        result = subprocess.run(
            ["uv", "run", "python", "scripts/import_all_artifact.py"],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        if result.returncode != 0:
            logger.error(f"All-firms import exited with code {result.returncode}")
            if result.stderr:
                logger.error(f"All-firms import stderr:\n{result.stderr[:500]}")
        else:
            for line in result.stdout.strip().split('\n'):
                if any(kw in line for kw in ('Import', 'inserted', 'updated', 'Complete', 'SUCCESS')):
                    logger.info(f"[All-import] {line.strip()}")
    except subprocess.TimeoutExpired:
        logger.error("All-firms import timed out (600s)")
    except Exception as e:
        logger.error(f"All-firms import error: {e}")
    logger.info("--- [Job End] All-Firms Artifact Import ---")

# 최적화 실패로 인한 일시 주석 처리
# def run_enricher_batch(limit=200):
#     """Enricher 배치 실행 - 태그 없는 과거 레포트 태그 추출 (주간 catch-up)"""
#     logger.info(f"--- [Job Start] Enricher Batch (limit={limit}) ---")
#     try:
#         from enricher import EnricherManager
#         enricher = EnricherManager()
#         result = enricher.enrich_pending(limit=limit)
#         logger.info(
#             f"[Enricher] batch 완료: total={result['total']}, "
#             f"enriched={result['enriched']}, errors={result['errors']}"
#         )
#     except Exception as e:
#         logger.error(f"[Enricher] batch failed: {e}")
#     logger.info("--- [Job End] Enricher Batch ---")

# 최적화 실패로 인한 일시 주석 처리
# def run_enricher_backfill(batch_size=30000, batches=1):
#     """Enricher 고속 백필 - 5분마다 3만건씩 처리 (~3분 소요)"""
#     logger.info(f"--- [Job Start] Enricher Backfill ({batch_size}건 x {batches}배치) ---")
#     try:
#         result = subprocess.run(
#             ["uv", "run", "enricher/backfill_sync.py", str(batch_size), str(batches)],
#             capture_output=True,
#             text=True,
#             check=False,
#             timeout=600,  # 10분 타임아웃
#         )
#         if result.returncode != 0:
#             logger.error(f"[Enricher] backfill exited with code {result.returncode}")
#             if result.stderr:
#                 logger.error(f"[Enricher] stderr:\n{result.stderr}")
#         else:
#             # 마지막 줄만 요약 출력
#             for line in result.stdout.strip().split('\n'):
#                 if '완료' in line or '평균' in line or '미처리' in line:
#                     logger.info(f"[Enricher] {line.strip()}")
#     except subprocess.TimeoutExpired:
#         logger.error("[Enricher] backfill timed out (30min)")
#     except Exception as e:
#         logger.error(f"[Enricher] backfill failed: {e}")
#     logger.info("--- [Job End] Enricher Backfill ---")

def run_ai_summary(limit):
    """AI 요약 배치 실행 (현재 미사용 - 주석 처리용)"""
    logger.info(f"--- AI Summary Batch Start (Limit: {limit}) ---")
    try:
        result = subprocess.run(
            ["uv", "run", "run/gemini_summary_batch.py", str(limit)],
            check=False
        )
        if result.returncode != 0:
            logger.error(f"Batch process exited with error code {result.returncode}")
    except Exception as e:
        logger.error(f"Execution Error: {e}")
    logger.info("--- AI Summary Batch End ---")

scheduler = BlockingScheduler()

# [스케줄 1] 메인 스크래퍼 (enrich + send): 30분 간격
scheduler.add_job(
    run_scraper,
    CronTrigger(minute='*/30', hour='0,5-12,14-23', jitter=300),
    id="main_scraper_job"
)

# [스케줄 2] LS 아티팩트 import: GitHub Actions 완료 시점에 맞춰 매시 05, 35분
#   LS cron: 0,30 → GitHub Actions가 :00, :30에 실행 → import는 :05, :35
scheduler.add_job(
    run_import_ls,
    CronTrigger(minute='5,35', hour='0,5-12,14-23', jitter=60),
    id="import_ls_artifact_job"
)

# [스케줄 3] 전체 증권사 아티팩트 import: GitHub Actions 완료 시점에 맞춰 매시 10, 40분
#   scrape-all cron: 5,35 → GitHub Actions가 :05, :35에 실행 → import는 :10, :40
scheduler.add_job(
    run_import_all,
    CronTrigger(minute='10,40', hour='0,5-12,14-23', jitter=60),
    id="import_all_artifact_job"
)

# [스케줄 4] Enricher 배치: 15분마다 2000건 인프로세스 (~28만건/35시간) -> 최적화 실패로 인한 일시 비활성화
# scheduler.add_job(
#     run_enricher_batch,
#     CronTrigger(minute='*/15', jitter=60),
#     kwargs={"limit": 2000},
#     id="enricher_batch_job"
# )

# [스케줄 3] Enricher subprocess 백필: 동시실행 충돌로 비활성화
# scheduler.add_job(
#     run_enricher_backfill,
#     CronTrigger(minute='*/5', jitter=30),
#     kwargs={"batch_size": 30000, "batches": 1},
#     id="enricher_backfill_job"
# )

# [스케줄 2] AI 요약: 일단 주석 처리 (필요 시 해제)
"""
scheduler.add_job(
    run_ai_summary,
    CronTrigger(minute='15,45', hour='0,5-12,13,14-23'),
    args=[20],
    id="summary_batch_20"
)

scheduler.add_job(
    run_ai_summary,
    CronTrigger(minute='0,15,30,45', hour='1-4'),
    args=[30],
    id="summary_batch_30"
)
"""

if __name__ == "__main__":
    logger.info("🚀 Master Scheduler starting up...")
    logger.info("Registered Jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"- {job.id}: {job.trigger}")
    
    # 시작 시 즉시 한 번 실행하려면 아래 주석 해제
    # run_scraper()
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.warning("Scheduler stopped.")
