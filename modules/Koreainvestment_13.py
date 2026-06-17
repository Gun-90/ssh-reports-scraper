# -*- coding:utf-8 -*-
"""한국투자증권 — anti-bot WAF 회피용 undetected-chromedriver + Xvfb 비헤드리스.

securities.koreainvestment.com 리서치(Strategy.jsp)는 자동화를 감지해 error.jsp로
리다이렉트한다. undetected-chromedriver를 Xvfb 가상 디스플레이에서 비헤드리스로
구동하면 통과된다. 리포트 PDF는 웹은 로그인 게이트이지만 파일서버
(file.truefriend.com/Storage/...)는 로그인 없이 직접 서빙한다.
"""
import os
import re
import time
import shutil
import asyncio
import urllib.parse
from datetime import datetime
from loguru import logger

import setuptools._distutils.version  # Python 3.12 distutils shim (uc 의존)
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.FirmInfo import FirmInfo
from models.ConfigManager import config

SEC_FIRM_ORDER = 13
DEFAULT_LIST_URL = "https://securities.koreainvestment.com/main/research/research/Strategy.jsp"
HOME_URL = "https://securities.koreainvestment.com/"
CHROMIUM = "/usr/bin/chromium"
SYS_DRIVER = "/usr/bin/chromedriver"


def _writable_driver():
    """uc는 드라이버 바이너리를 패치(쓰기)하므로 쓰기 가능한 복사본 경로를 준다."""
    dst = "/tmp/kis_chromedriver"
    try:
        if not os.path.exists(dst):
            shutil.copy(SYS_DRIVER, dst)
            os.chmod(dst, 0o755)
    except Exception as e:
        logger.error(f"KIS driver copy 실패: {e}")
        return SYS_DRIVER
    return dst


def _kis_onclick_to_pdf(onclick: str) -> str:
    """새 prePdfFileView(...) onclick → file.truefriend.com 직링크."""
    if not onclick:
        return ""
    s = onclick.replace("&amp;", "&")
    m = re.search(r"prePdfFileView\d?\((.*)\)", s)
    if not m:
        return ""
    parts = [p.strip().strip("'\"") for p in m.group(1).split(",")]
    if len(parts) < 4:
        return ""
    filepath_q, filename, option, date = parts[0], parts[1], parts[2], parts[3]
    air = parts[4] if len(parts) > 4 else "N"
    kor = parts[5] if len(parts) > 5 else "Y"
    spec = parts[6] if len(parts) > 6 else "N"
    r = Koreainvestment_MAKE_LIST_ARTICLE_URL(filepath_q, filename, option, date, air, kor, spec)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r).query)
    fp = q.get("filepath", [""])[0]
    fn = q.get("filename", [""])[0]
    if fp and fn:
        return f"http://file.truefriend.com/Storage/{fp}/{fn}"
    return r


def _new_driver():
    opts = uc.ChromeOptions()
    for a in ["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1366,900", "--lang=ko-KR"]:
        opts.add_argument(a)
    opts.binary_location = CHROMIUM
    return uc.Chrome(options=opts, driver_executable_path=_writable_driver(),
                     browser_executable_path=CHROMIUM, version_main=148,
                     headless=False, use_subprocess=True)


def _scrape_kis_sync(list_url: str):
    out = []
    # 동시 스크래핑 부하로 chromium 기동이 실패("cannot connect to chrome")할 수 있어 재시도
    driver = None
    for attempt in range(1, 4):
        try:
            driver = _new_driver()
            break
        except Exception as e:
            logger.warning(f"KIS chromium 기동 실패 {attempt}/3: {str(e)[:80]}")
            try:
                if driver: driver.quit()
            except Exception:
                pass
            driver = None
            time.sleep(4)
    if driver is None:
        logger.error("KIS: chromium 기동 3회 실패")
        return out
    try:
        driver.set_page_load_timeout(60)
        driver.get(HOME_URL)
        time.sleep(4)
        driver.get(list_url)
        time.sleep(8)
        if "error.jsp" in driver.current_url:
            logger.error("KIS: anti-bot 차단(error.jsp)")
            return out
        firm_info = FirmInfo(SEC_FIRM_ORDER, 0)
        btns = driver.find_elements(By.XPATH, "//a[contains(@onclick, 'prePdfFileView')]")
        logger.info(f"KIS: {len(btns)} report links on page")
        for btn in btns:
            onclick = btn.get_attribute("onclick") or ""
            pdf = _kis_onclick_to_pdf(onclick)
            if not pdf:
                continue
            title, writer = "", ""
            try:
                li = btn.find_element(By.XPATH, "./ancestor::li[1]")
                try:
                    title = li.find_element(By.CSS_SELECTOR, "span.body_tit").text.strip()
                except Exception:
                    title = ""
                ems = li.find_elements(By.CSS_SELECTOR, "span.tit_info em")
                if ems:
                    writer = (ems[0].text or "").strip()
            except Exception:
                pass
            dm = re.search(r"'(\d{4}[-./]\d{2}[-./]\d{2})'", onclick.replace("&amp;", "&"))
            reg_dt = re.sub(r"[-./]", "", dm.group(1)) if dm else ""
            out.append({
                "sec_firm_order": SEC_FIRM_ORDER, "article_board_order": 0,
                "firm_nm": firm_info.get_firm_name(), "reg_dt": reg_dt,
                "article_title": title or "(제목없음)",
                "article_url": pdf, "download_url": pdf, "telegram_url": pdf, "pdf_url": pdf,
                "writer": writer, "key": pdf, "report_unique_key": pdf,
                "save_time": datetime.now().isoformat(), "mkt_tp": "KR",
            })
    except Exception as e:
        logger.error(f"Error during KoreaInvestment scraping: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
    # 동일 pdf_url 중복 제거
    uniq = {}
    for r in out:
        uniq.setdefault(r["key"], r)
    return list(uniq.values())


async def Koreainvestment_selenium_checkNewArticle():
    urls = config.get_urls("Koreainvestment_13")
    list_url = urls[0] if urls else DEFAULT_LIST_URL
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(None, _scrape_kis_sync, list_url)
        logger.info(f"Total articles collected: {len(res)}")
        return res
    except Exception as e:
        logger.error(f"Koreainvestment error: {e}")
        return []


def Koreainvestment_MAKE_LIST_ARTICLE_URL(filepath, filename, option, datasubmitdate, air_yn, kor_yn, special_yn):
    filename = urllib.parse.quote(filename)
    host_name = "http://research.truefriend.com/streamdocs/openResearch"
    host_name2, host_name3 = "https://kis-air.com/kor/", "https://kis-air.com/us/"

    if filepath.startswith("?") or filepath.startswith("&"):
        filepath = filepath[1:]

    params = filepath.split("&")
    if len(params) == 2:
        p1, p2 = params[0], params[1]
        if (p1 == 'category1=01' and p2 in ['category2=01', 'category2=02', 'category2=03', 'category2=04', 'category2=05']):
            filepath = "research/research01"
        elif (p1 == 'category1=02' and p2 in ['category2=01', 'category2=02', 'category2=03', 'category2=04', 'category2=06', 'category2=08', 'category2=09', 'category2=10', 'category2=11', 'category2=12', 'category2=13', 'category2=14']):
            filepath = "research/research02"
        elif (p1 == 'category1=03' and p2 in ['category2=01', 'category2=02', 'category2=03']):
            filepath = "research/research03"
        elif (p1 == 'category1=04' and p2 in ['category2=00', 'category2=01', 'category2=02', 'category2=03']):
            filepath = "research/research04"
        elif p1 == 'category1=05':
            filepath = "research/research05"
        elif p1 == 'category1=07' and p2 == 'category2=01':
            filepath = "research/research07"
        elif p1 == 'category1=08' and p2 in ['category2=03', 'category2=04', 'category2=05']:
            filepath = "research/research08"
        elif p1 == 'category1=06' and p2 in ['category2=01', 'category2=02']:
            filepath = "research/research06"
        elif p1 == 'category1=09' and p2 == 'category2=00':
            filepath = "research/research11"
        elif p1 == 'category1=10' and p2 in ['category2=01', 'category2=04', 'category2=06']:
            if p2 == 'category2=06': filepath = "research/research_emailcomment"
            elif p2 == 'category2=04': filepath = "research/china"
            else: filepath = "research/research10"
        elif p1 == 'category1=14' and p2 == 'category2=01':
            filepath = "research/research14"
        elif p1 == 'category1=13' and p2 == 'category2=01':
            filepath = "research/research11"
        elif p1 == 'category1=17':
            filepath = "research/research17"
        elif p1 == 'category1=15' and p2 == 'category2=01':
            filepath = "research/research01"
        elif p1 == 'category1=16' and p2 == 'category2=01':
            filepath = "research/research15"

    if not option: option = "01"

    if params == ['category1=15', 'category2=01']:
        datasubmitdate = datasubmitdate.replace(".", "-")
        return f"{host_name2 if kor_yn == 'Y' else host_name3}{datasubmitdate}/{'special' if special_yn == 'Y' else 'daily'}"
    else:
        return f"{host_name}?filepath={urllib.parse.quote(filepath)}&filename={filename}&option={option}"


if __name__ == "__main__":
    results = asyncio.run(Koreainvestment_selenium_checkNewArticle())
    logger.info(f"Total articles fetched: {len(results)}")
