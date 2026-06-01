# -*- coding:utf-8 -*- 
from loguru import logger
import gc
import requests
import time
from datetime import datetime

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.FirmInfo import FirmInfo
from models.WebScraper import SyncWebScraper
from models.ConfigManager import config


def Hmsec_checkNewArticle():
    sec_firm_order      = 9
    json_data_list = []

    requests.packages.urllib3.disable_warnings()

    TARGET_URL_TUPLE = config.get_urls("Hmsec_9")
    if not TARGET_URL_TUPLE:
        logger.warning("No URLs found for Hmsec_9")
        return []

    for article_board_order, TARGET_URL in enumerate(TARGET_URL_TUPLE):
        firm_info = FirmInfo(
            sec_firm_order=sec_firm_order,
            article_board_order=article_board_order
        )

        page = 1
        total_pages = None
        max_pages = 5  # 보드당 최대 5페이지(40건) — 30분 주기에 충분
        board_articles = 0

        while True:
            if page > max_pages:
                break
            payload = {"curPage": page}
            scraper = SyncWebScraper(TARGET_URL, firm_info)

            try:
                jres = scraper.PostJson(params=payload)
            except Exception as e:
                logger.warning(f"Hmsec page {page} fetch failed: {e}")
                break

            if not jres or not isinstance(jres, dict):
                break

            soupList = jres.get('data_list', [])
            if not soupList:
                break

            if total_pages is None:
                paging = jres.get('paging', {})
                total_pages = paging.get('totalPages', 1)

            for item in soupList:
                download_url = f"https://www.hmsec.com/documents/research/{item['UPLOAD_FILE1']}"
                article_url = f"https://docs.hmsec.com/SynapDocViewServer/job?fid={download_url}&sync=true&fileType=URL&filePath={download_url}"
                writer = (item.get('NAME') or '').strip()
                reg_dt = (item.get('REG_DATE') or '').strip()

                json_data_list.append({
                    "sec_firm_order": sec_firm_order,
                    "article_board_order": article_board_order,
                    "firm_nm": firm_info.get_firm_name(),
                    "article_title": item['SUBJECT'],
                    "reg_dt": reg_dt,
                    "article_url": article_url,
                    "pdf_url": download_url,
                    "download_url": download_url,
                    "telegram_url": article_url,
                    "key": article_url,
                    "writer": writer,
                    "save_time": datetime.now().isoformat()
                })
                board_articles += 1

            page += 1
            if total_pages and page > total_pages:
                break
            time.sleep(0.3)  # polite delay

        logger.info(f"Hmsec board={article_board_order}: {board_articles} articles ({page-1} pages)")

    gc.collect()
    logger.info(f"Hmsec total: {len(json_data_list)} articles")
    return json_data_list
