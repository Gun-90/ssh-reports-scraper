# -*- coding:utf-8 -*-
import gc
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from models.ConfigManager import config
from models.FirmInfo import FirmInfo

# BASE_URL은 secrets.json의 첫 번째 URL에서 추출 (git에 URL 노출 방지)
_urls_tmp = config.get_urls("Heungkuk_28")
if _urls_tmp:
    _p = urlparse(_urls_tmp[0])
    BASE_URL = f"{_p.scheme}://{_p.netloc}"
else:
    BASE_URL = ""
SEC_FIRM_ORDER = 28


def _normalize_reg_dt(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    m = re.search(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})", text)
    if m:
        y, mm, dd = m.groups()
        return f"{int(y):04d}{int(mm):02d}{int(dd):02d}"

    m = re.search(
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(\d{1,2})\s+\d{2}:\d{2}:\d{2}\s+\w+\s+(20\d{2})\b",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                  "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
        mon, dd, y = m.groups()
        return f"{int(y):04d}{months[mon.lower()]:02d}{int(dd):02d}"

    digits = re.sub(r"[^0-9]", "", text)
    return digits[:8] if len(digits) >= 8 else ""


def Heungkuk_checkNewArticle():
    requests.packages.urllib3.disable_warnings()
    urls = config.get_urls("Heungkuk_28")
    if not urls:
        logger.error("Heungkuk_28 URLs are not configured.")
        return []

    json_data_list = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"{BASE_URL}/research/index.do",
    })

    for board_order, list_url in enumerate(urls):
        firm_info = FirmInfo(sec_firm_order=SEC_FIRM_ORDER, article_board_order=board_order)
        try:
            resp = session.get(list_url, timeout=20, verify=False)
            resp.raise_for_status()
            resp.encoding = "euc-kr"
            html = resp.text
        except Exception as e:
            logger.error(f"Heungkuk list fetch failed: {list_url} ({e})")
            continue

        soup = BeautifulSoup(html, "html.parser")
        board_match = re.search(r"/research/([^/]+)/list\.do", list_url)
        board_path = board_match.group(1) if board_match else "company"

        rows = []
        for tr in soup.select("table.data_list_x tbody tr"):
            a = tr.select_one("a[onclick*=\"nav.go('view'\"]")
            if not a:
                continue
            onclick = a.get("onclick", "")
            key_match = re.search(r"key=(\d+)", onclick)
            if not key_match:
                continue

            view_key = int(key_match.group(1))
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            cells = tr.find_all("td")
            if len(cells) < 5:
                continue

            writer = re.sub(r"\s+", " ", cells[2].get_text(" ", strip=True))
            reg_dt = _normalize_reg_dt(cells[3].get_text(" ", strip=True))
            view_url = f"{BASE_URL}/research/{board_path}/view.do?key={view_key}"

            # 간단한 PDF URL 추정 (download.do?type=Board&key=N 패턴)
            pdf_key = 2 * view_key - 11927  # 휴리스틱 오프셋
            download_url = f"{BASE_URL}/download.do?type=Board&key={pdf_key}"

            json_data_list.append({
                "sec_firm_order": SEC_FIRM_ORDER,
                "article_board_order": board_order,
                "firm_nm": firm_info.get_firm_name(),
                "reg_dt": reg_dt,
                "download_url": download_url,
                "telegram_url": download_url,
                "pdf_url": download_url,
                "article_title": title,
                "article_url": view_url,
                "writer": writer,
                "key": download_url,
                "save_time": datetime.now().isoformat(),
            })

        logger.info(f"Heungkuk board={board_order}: {len(json_data_list)} rows")

    gc.collect()
    return json_data_list


if __name__ == "__main__":
    result = Heungkuk_checkNewArticle()
    logger.info(f"Heungkuk total rows: {len(result)}")
