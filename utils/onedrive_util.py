# -*- coding: utf-8 -*-
import os
import re
import asyncio
import datetime
import tempfile
import subprocess
from loguru import logger

RCLONE_REMOTE = "onedrive:증권리포트"
RCLONE_BIN = os.getenv("RCLONE_BIN", "/usr/bin/rclone")
RCLONE_CONFIG = os.getenv("RCLONE_CONFIG", "/home/appuser/.config/rclone/rclone.conf")

# rclone subprocess는 컨테이너의 SOCKS5 프록시 env(HTTP_PROXY 등)를 상속하면
# OneDrive 업로드가 실패한다. 프록시 변수를 제거한 환경을 따로 만들어 전달한다.
_PROXY_KEYS = {"http_proxy", "https_proxy", "all_proxy", "ftp_proxy"}
_CLEAN_ENV = {k: v for k, v in os.environ.items() if k.lower() not in _PROXY_KEYS}

_FIRM_NAME_MAP = {
    0: "LS증권", 1: "신한투자", 2: "NH투자", 3: "하나증권",
    4: "KB증권", 5: "삼성증권", 6: "상상인", 7: "신영증권",
    8: "미래에셋", 9: "현대모비스", 10: "키움증권", 11: "DS투자",
    12: "유진투자", 13: "한국투자", 14: "다올투자", 15: "토스증권",
    16: "리딩투자", 17: "대신증권", 18: "아이엠증권", 19: "DB금융",
    20: "메리츠증권", 21: "한화투자", 22: "한양증권", 23: "BNK투자",
    24: "교보증권", 25: "IBK투자", 26: "SK증권", 27: "유안타증권",
    28: "흥국증권",
}

def _sanitize(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    return name.strip()[:80]

def _rclone_available() -> bool:
    return os.path.isfile(RCLONE_BIN) and os.access(RCLONE_BIN, os.X_OK)

async def upload_pdf_to_onedrive(
    pdf_url: str,
    sec_firm_order: int,
    article_title: str,
    reg_dt: str,
    session=None,
) -> str | None:
    if not _rclone_available():
        logger.warning(f"[OneDrive] rclone not found at {RCLONE_BIN}, skipping upload")
        return None
    if not pdf_url or not pdf_url.startswith("http"):
        return None

    firm_name = _FIRM_NAME_MAP.get(sec_firm_order, f"firm_{sec_firm_order}")
    year_month = reg_dt[:6] if reg_dt and len(reg_dt) >= 6 else "000000"
    safe_title = _sanitize(article_title or "untitled")
    remote_path = f"{RCLONE_REMOTE}/{firm_name}/{year_month}/{reg_dt}_{safe_title}.pdf"

    try:
        import aiohttp
        close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True

        try:
            async with session.get(pdf_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    logger.warning(f"[OneDrive] PDF download failed ({resp.status}): {pdf_url}")
                    return None
                pdf_bytes = await resp.read()
        finally:
            if close_session:
                await session.close()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            proc = await asyncio.create_subprocess_exec(
                RCLONE_BIN, "copyto",
                "--config", RCLONE_CONFIG,
                tmp_path, remote_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_CLEAN_ENV,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                logger.error(f"[OneDrive] rclone failed: {stderr.decode()[:200]}")
                return None
            logger.success(f"[OneDrive] Uploaded: {remote_path}")
            return remote_path
        finally:
            os.unlink(tmp_path)

    except asyncio.TimeoutError:
        logger.error(f"[OneDrive] Upload timeout: {pdf_url}")
        return None
    except Exception as e:
        logger.error(f"[OneDrive] Upload error: {e}")
        return None


async def upload_batch(records: list[dict], concurrency: int = 1, delay: float = 0.5) -> dict[str, str]:
    """records: list of dicts with keys pdf_url, sec_firm_order, article_title, reg_dt, key"""
    results = {}
    semaphore = asyncio.Semaphore(concurrency)

    async def _upload_one(r):
        async with semaphore:
            key = r.get("key") or r.get("pdf_url", "")
            path = await upload_pdf_to_onedrive(
                pdf_url=r.get("pdf_url") or r.get("telegram_url", ""),
                sec_firm_order=r.get("sec_firm_order", -1),
                article_title=r.get("article_title", ""),
                reg_dt=str(r.get("reg_dt", "")),
            )
            if path:
                results[key] = path
            await asyncio.sleep(delay)

    await asyncio.gather(*[_upload_one(r) for r in records])
    return results


# --- 증분 업로드 (스크래퍼 파이프라인에서 호출) ---
# 업로드 성공 시 tbl_sec_reports.archive_path에 OneDrive 경로를 기록하고,
# archive_path 미기록 여부를 중복 방지 기준으로 사용한다(별도 매니페스트 불필요).

async def upload_recent_to_onedrive(db, days: int = 2) -> None:
    """최근 days일 내 pdf_url 있고 archive_path 미기록인 리포트를 OneDrive 업로드.

    성공 건은 archive_path = OneDrive 경로로 UPDATE. 스키마 변경 없이 기존
    archive_path 컬럼만 채운다. 스크래퍼 main()의 enrich 직후 호출된다.
    """
    if not _rclone_available():
        logger.warning(f"[OneDrive] rclone 미발견({RCLONE_BIN}) — 업로드 스킵")
        return
    if not hasattr(db, "_execute"):
        logger.error("[OneDrive] db._execute 없음 — archive_path 기록 불가, 업로드 스킵")
        return
    since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y%m%d")
    rows = db._fetchall(
        "SELECT report_id, sec_firm_order, article_title, reg_dt, pdf_url "
        "FROM tbl_sec_reports "
        "WHERE reg_dt >= %s AND pdf_url IS NOT NULL AND LENGTH(pdf_url) > 0 "
        "AND (archive_path IS NULL OR archive_path = '') "
        "ORDER BY reg_dt",
        (since,),
    )
    records = [{**dict(r), "key": str(r["report_id"])} for r in rows]
    if not records:
        logger.info(f"[OneDrive] 신규 업로드 대상 없음 (reg_dt>={since})")
        return
    logger.info(f"[OneDrive] {len(records)}건 업로드 시작 (reg_dt>={since})")
    uploaded = await upload_batch(records, concurrency=2, delay=0.3)
    ok = 0
    for r in records:
        path = uploaded.get(r["key"])
        if not path:
            continue
        try:
            db._execute(
                "UPDATE tbl_sec_reports SET archive_path = %s WHERE report_id = %s",
                (path, int(r["report_id"])),
            )
            ok += 1
        except Exception as e:
            logger.error(f"[OneDrive] archive_path 기록 실패 (report_id={r['report_id']}): {e}")
    logger.success(f"[OneDrive] {ok}/{len(records)}건 업로드+archive_path 기록 완료")
