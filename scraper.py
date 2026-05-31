# -*- coding:utf-8 -*- 
import os
import sys
import asyncio
import time
import argparse
import datetime
from loguru import logger
from dotenv import load_dotenv

# 공통 로그 설정 적용
from utils.logger_util import setup_logger
setup_logger("scraper")

# --- 모듈 임포트 ---
from utils.telegram_util import sendMarkDownText
from utils.sqlite_util import convert_sql_to_telegram_messages
from models.db_factory import get_db

# business modules — GitHub Actions standalone 스크래퍼로 모두 분리됨
# 비상시 EMERGENCY_SCRAPE=1 환경변수로 서버 직접 스크래핑 활성화 가능
_EMERGENCY = os.getenv("EMERGENCY_SCRAPE", "0") == "1"

if _EMERGENCY:
    from modules.Koreainvestment_13 import Koreainvestment_selenium_checkNewArticle
    from modules.ShinHanInvest_1 import ShinHanInvest_checkNewArticle
    from modules.NHQV_2 import NHQV_checkNewArticle
    from modules.HANA_3 import HANA_checkNewArticle
    from modules.KBsec_4 import KB_checkNewArticle
    from modules.Samsung_5 import Samsung_checkNewArticle
    from modules.Sangsanginib_6 import Sangsanginib_checkNewArticle
    from modules.Shinyoung_7 import Shinyoung_checkNewArticle
    from modules.Miraeasset_8 import Miraeasset_checkNewArticle
    from modules.Hmsec_9 import Hmsec_checkNewArticle
    from modules.Kiwoom_10 import Kiwoom_checkNewArticle
    from modules.DS_11 import DS_checkNewArticle
    from modules.DAOL_14 import DAOL_checkNewArticle
    from modules.TOSSinvest_15 import TOSSinvest_checkNewArticle
    from modules.Leading_16 import Leading_checkNewArticle
    from modules.Daeshin_17 import Daeshin_checkNewArticle
    from modules.DBfi_19 import DBfi_checkNewArticle, DBfi_detail
    from modules.MERITZ_20 import MERITZ_checkNewArticle
    from modules.Hanwhawm_21 import Hanwha_checkNewArticle
    from modules.Hygood_22 import Hanyang_checkNewArticle
    from modules.BNKfn_23 import BNK_checkNewArticle
    from modules.Kyobo_24 import Kyobo_checkNewArticle
    from modules.IBKs_25 import IBK_checkNewArticle
    from modules.SKS_26 import Sks_checkNewArticle
    from modules.Yuanta_27 import Yuanta_checkNewArticle
else:
    # enrich_data()에서 DBfi_detail만 여전히 필요함
    from modules.DBfi_19 import DBfi_detail

load_dotenv()
token = os.getenv('TELEGRAM_BOT_TOKEN_REPORT_ALARM_SECRET')
chat_id = os.getenv('TELEGRAM_CHANNEL_ID_REPORT_ALARM')
SCRAPER_STALE_DAYS = int(os.getenv("SCRAPER_STALE_DAYS", "5"))
SCRAPER_HEALTH_ERRORS = []

# 모듈별 stale 임계값 오버라이드 (예: "TOSSinvest_checkNewArticle=30,OtherScraper=14")
_STALE_OVERRIDES = {}
_raw_overrides = os.getenv("SCRAPER_STALE_OVERRIDES", "")
if _raw_overrides:
    for pair in _raw_overrides.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            try:
                _STALE_OVERRIDES[k.strip()] = int(v.strip())
            except ValueError:
                pass


def log_scraper_health(name, rows):
    if not isinstance(rows, list):
        msg = f"{name} returned non-list result: {type(rows)}"
        SCRAPER_HEALTH_ERRORS.append(msg)
        logger.error(msg)
        return

    if not rows:
        msg = f"{name} returned 0 articles. Check source API, selector, or credentials."
        SCRAPER_HEALTH_ERRORS.append(msg)
        logger.error(msg)
        return

    reg_dates = sorted({
        str(row.get("reg_dt", ""))[:8]
        for row in rows
        if row.get("reg_dt")
    })
    if not reg_dates:
        msg = f"{name} returned {len(rows)} articles but no reg_dt values."
        SCRAPER_HEALTH_ERRORS.append(msg)
        logger.error(msg)
        return

    min_reg_dt = reg_dates[0]
    max_reg_dt = reg_dates[-1]
    logger.info(f"{name} => Found {len(rows)} articles (reg_dt {min_reg_dt}~{max_reg_dt})")

    try:
        max_date = datetime.datetime.strptime(max_reg_dt, "%Y%m%d").date()
        stale_days = _STALE_OVERRIDES.get(name, SCRAPER_STALE_DAYS)
        stale_cutoff = datetime.datetime.now().date() - datetime.timedelta(days=stale_days)
        if max_date < stale_cutoff:
            msg = (
                f"{name} latest reg_dt is stale: {max_reg_dt} "
                f"(older than {stale_days} days)"
            )
            SCRAPER_HEALTH_ERRORS.append(msg)
            logger.error(msg)
    except ValueError:
        msg = f"{name} returned invalid max reg_dt: {max_reg_dt}"
        SCRAPER_HEALTH_ERRORS.append(msg)
        logger.error(msg)


async def enrich_data():
    logger.info("Starting data enrichment process...")
    db = get_db()
    from models.FirmInfo import FirmInfo

    # KST 기준 시간 확인 (20시 이후 = 유휴시간 = 전체 backlog 정리)
    import pytz
    from datetime import datetime
    kst_hour = datetime.now(pytz.timezone('Asia/Seoul')).hour
    is_idle_time = kst_hour >= 20 or kst_hour < 6

    for sec_firm_order in range(len(FirmInfo.firm_names)):
        firm_info = FirmInfo(sec_firm_order=sec_firm_order, article_board_order=0)
        firm_name = firm_info.get_firm_name()

        if firm_name and firm_info.telegram_update_required:
            # 최근 3일 비어있는 항목은 항상 후처리
            records = await db.fetch_all_empty_telegram_url_articles(firm_info=firm_info, days_limit=3)
            if not records: continue

            logger.info(f"[{firm_name}] Found {len(records)} records for enrichment (최근 3일).")
            try:
                if sec_firm_order == 19:  # DB증권
                    update_records = await DBfi_detail(articles=records, firm_info=firm_info, db=db)
                    # DBfi_detail 내부에서 건별 DB 업데이트를 이미 수행함
                    success_count = sum(1 for r in update_records if r.get('telegram_url', '').startswith('https://whub.dbsec.co.kr/pv/gate'))
                    if success_count:
                        logger.success(f"[DBfi] {success_count}/{len(update_records)}건 gate URL 복구 완료")

                    # 유휴시간(20시~06시) 전체 backlog 정리
                    if is_idle_time:
                        backlog = db._fetchall('''
                            SELECT report_id, article_title, writer, telegram_url, article_url, reg_dt, key
                            FROM tbl_sec_reports
                            WHERE sec_firm_order = 19
                              AND (telegram_url IS NULL OR telegram_url = ''
                                   OR telegram_url NOT LIKE 'https://whub.dbsec.co.kr/pv/gate%%')
                              AND key IS NOT NULL AND key != ''
                            ORDER BY save_time DESC
                            LIMIT 200
                        ''')
                        if backlog:
                            logger.info(f"[DBfi][유휴] 전체 backlog {len(backlog)}건 재처리...")
                            fixed = await DBfi_detail(articles=backlog, firm_info=firm_info, db=db)
                            fixed_count = sum(1 for r in fixed if r.get('telegram_url', '').startswith('https://whub.dbsec.co.kr/pv/gate'))
                            logger.success(f"[DBfi][유휴] {fixed_count}/{len(backlog)}건 gate URL 복구 완료")
                elif sec_firm_order == 0:  # LS → GitHub Actions standalone으로 분리됨
                    pass
                elif sec_firm_order == 11:  # DS
                    pass
                logger.success(f"[{firm_name}] Enrichment completed.")
            except Exception as e:
                logger.error(f"[{firm_name}] Enrichment failed: {e}")


async def daily_send_report(date_str=None):
    db = get_db()
    rows = await db.daily_select_data(date_str=date_str, type='send')
    if rows:
        messages = convert_sql_to_telegram_messages(rows)
        logger.info(f"Sending {len(messages)} messages...")
        for i, msg in enumerate(messages):
            logger.debug(f"Message {i+1} preview:\n{msg[:500]}...")
        success = True
        for msg in messages:
            try:
                await sendMarkDownText(token=token, chat_id=chat_id, sendMessageText=msg)
            except Exception as e:
                logger.error(f"Telegram error: {e}")
                success = False
        if success:
            await db.daily_update_data(date_str=date_str, fetched_rows=rows, type='send')
            logger.success("Daily report sent and DB updated.")


# ── Emergency scrape helpers (EMERGENCY_SCRAPE=1 전용) ──

def run_sync_scrapers(sync_funcs, total_data):
    for func in sync_funcs:
        try:
            logger.info(f"Scraping (Sync): {func.__name__}")
            res = func()
            if res:
                total_data.extend(res)
            log_scraper_health(func.__name__, res)
            time.sleep(1)
        except Exception as e:
            msg = f"Sync Scraper Error ({func.__name__}): {e}"
            SCRAPER_HEALTH_ERRORS.append(msg)
            logger.error(msg)


async def run_async_scrapers(async_funcs, total_data):
    logger.info(f"Launching {len(async_funcs)} async scrapers...")
    tasks = []
    task_names = []

    for f in async_funcs:
        try:
            if not callable(f):
                continue
            res = f()
            if asyncio.iscoroutine(res):
                tasks.append(res)
                task_names.append(f.__name__)
            elif isinstance(res, list):
                total_data.extend(res)
                log_scraper_health(f.__name__, res)
            elif res is not None:
                msg = f"{f.__name__} returned unexpected type: {type(res)}"
                SCRAPER_HEALTH_ERRORS.append(msg)
                logger.error(msg)
        except Exception as e:
            msg = f"Error calling scraper {f.__name__}: {e}"
            SCRAPER_HEALTH_ERRORS.append(msg)
            logger.error(msg)

    if not tasks:
        return

    logger.debug(f"Gathering {len(tasks)} actual coroutines: {task_names}")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for idx, res in enumerate(results):
        name = task_names[idx]
        if isinstance(res, Exception):
            msg = f"Async Scraper Error ({name}): {res}"
            SCRAPER_HEALTH_ERRORS.append(msg)
            logger.error(msg)
        elif isinstance(res, list):
            total_data.extend(res)
            log_scraper_health(name, res)
        elif res is not None:
            msg = f"{name} returned non-list result: {type(res)}"
            SCRAPER_HEALTH_ERRORS.append(msg)
            logger.error(msg)


async def _emergency_scrape(db):
    """비상시 서버 직접 스크래핑 (EMERGENCY_SCRAPE=1)."""
    logger.warning("=== EMERGENCY MODE: 서버 직접 스크래핑 활성화 ===")
    total_data = []

    sync_funcs = [
        Miraeasset_checkNewArticle, Sks_checkNewArticle,
        Samsung_checkNewArticle, Shinyoung_checkNewArticle, Hmsec_checkNewArticle,
        TOSSinvest_checkNewArticle, DS_checkNewArticle
    ]
    async_functions = [
        Koreainvestment_selenium_checkNewArticle,
        ShinHanInvest_checkNewArticle, Leading_checkNewArticle,
        NHQV_checkNewArticle, HANA_checkNewArticle, KB_checkNewArticle,
        Sangsanginib_checkNewArticle, Kiwoom_checkNewArticle,
        DAOL_checkNewArticle, Daeshin_checkNewArticle,
        DBfi_checkNewArticle,
        MERITZ_checkNewArticle, Hanwha_checkNewArticle, Hanyang_checkNewArticle,
        BNK_checkNewArticle, Kyobo_checkNewArticle, IBK_checkNewArticle,
        Yuanta_checkNewArticle
    ]

    run_sync_scrapers(sync_funcs, total_data)
    await run_async_scrapers(async_functions, total_data)

    if total_data:
        unique = {d.get("key"): d for d in total_data if d.get("key")}
        total_list = list(unique.values())
        try:
            ins, upd = db.insert_json_data_list(total_list)
            logger.success(f"[EMERGENCY] DB Sync: {ins} new, {upd} updated.")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[EMERGENCY] DB error: {e}")
    else:
        logger.warning("[EMERGENCY] No data scraped.")


async def main(date_str=None):
    logger.info("=================== SCRAPER START ===================")
    db = get_db()

    # ── GitHub Actions 전환 완료: 기본 모드는 enrich + send 만 수행 ──
    # ── EMERGENCY_SCRAPE=1 시 서버 직접 스크래핑으로 폴백 ──
    if _EMERGENCY:
        await _emergency_scrape(db)

    await enrich_data()

    # 발송 전에 DB 연결을 새로 하거나 세션을 확실히 분리하여 최신 데이터를 가져옴
    await daily_send_report(date_str=date_str)
    logger.info("=================== SCRAPER END =====================")
    if SCRAPER_HEALTH_ERRORS:
        joined = "; ".join(SCRAPER_HEALTH_ERRORS)
        raise RuntimeError(f"Scraper health check failed: {joined}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('date', type=str, nargs='?', default=None)
    args = parser.parse_args()
    asyncio.run(main(date_str=args.date))
