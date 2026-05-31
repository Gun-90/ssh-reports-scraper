# -*- coding:utf-8 -*- 
from loguru import logger
import gc
import requests
import re
from datetime import datetime

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.FirmInfo import FirmInfo
from models.WebScraper import SyncWebScraper
from models.ConfigManager import config

def TOSSinvest_checkNewArticle():
    sec_firm_order      = 15
    json_data_list = []

    requests.packages.urllib3.disable_warnings()
 
    TARGET_URL_TUPLE = config.get_urls("TOSSinvest_15")
    
    for article_board_order, BASE_URL in enumerate(TARGET_URL_TUPLE):
        firm_info = FirmInfo(
            sec_firm_order=sec_firm_order,
            article_board_order=article_board_order
        )

        # ── 페이징 처리: page=0부터 totalPageCount까지 순회 ──
        page = 0
        total_pages = None
        while True:
            paged_url = re.sub(r'page=\d+', f'page={page}', BASE_URL)
            if 'page=' not in paged_url:
                paged_url += ('&' if '?' in paged_url else '?') + f'page={page}'

            scraper = SyncWebScraper(paged_url, firm_info)
            try:
                jres = scraper.GetJson()
            except Exception as e:
                logger.error(f"TOSS page {page} fetch failed: {e}")
                break

            soupList = jres.get('result', {}).get('list', [])
            if not soupList:
                break

            # 첫 페이지만 totalPageCount 확인
            if total_pages is None:
                paging = jres.get('result', {}).get('pagingParam', {})
                total_pages = paging.get('totalPageCount', 1)
                logger.info(f"TOSS Scraper [{firm_info.get_firm_name()}] board={article_board_order}: "
                           f"totalPages={total_pages}, size={len(soupList)}")

            for item in soupList:
                title = item.get('title', '')
                download_url = ''
                if item.get('files'):
                    download_url = item['files'][0].get('filePath', '')
                if not download_url:
                    download_url = item.get('contentImage', '')

                reg_dt = item.get('createdAt', '').split("T")[0]

                # writer: author 필드 우선, 없으면 contents에서 추출
                writer = item.get('author', '')
                if not writer:
                    contents = item.get('contents', '')
                    m = re.search(r'작성자[:\s]*([^<\n]+)', contents)
                    if m:
                        writer = m.group(1).strip()

                # mkt_tp: English 카테고리면 GLOBAL
                cat_name = item.get('category', {}).get('categoryName', '')
                mkt_tp = "GLOBAL" if 'english' in cat_name.lower() else "KR"

                json_data_list.append({
                    "sec_firm_order": sec_firm_order,
                    "article_board_order": article_board_order,
                    "firm_nm": firm_info.get_firm_name(),
                    "reg_dt": re.sub(r"[-./]", "", reg_dt),
                    "download_url": download_url,
                    "telegram_url": download_url,
                    "article_title": title,
                    "writer": writer,
                    "mkt_tp": mkt_tp,
                    "key": download_url,
                    "save_time": datetime.now().isoformat()
                })

            page += 1
            if total_pages and page >= total_pages:
                break

    # 메모리 정리
    gc.collect()

    logger.info(f"TOSS Scraper: total {len(json_data_list)} articles collected")
    return json_data_list
