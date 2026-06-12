# -*- coding:utf-8 -*-
"""상상인증권 — 서버 모듈 (scraper.py fallback).
공통 코어 scrapers/sangsangin_core.py 사용 → GA standalone과 로직 통일."""
import asyncio
import os
import sys

from loguru import logger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.ConfigManager import config
from scrapers.sangsangin_core import scrape_sangsangin


async def Sangsanginib_checkNewArticle():
    urls = config.get_urls("Sangsanginib_6")
    if not urls:
        logger.warning("No URLs found for Sangsanginib_6")
        return []

    logger.debug("Sangsangin Scraper Start: 상상인증권 via scrapers.sangsangin_core")

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, scrape_sangsangin, urls[0])
        logger.info(f"Sangsangin Scraper: Found {len(result)} articles")
        return result
    except Exception as e:
        logger.error(f"Error scraping Sangsangin: {e}")
        return []


async def main():
    result = await Sangsanginib_checkNewArticle()
    logger.info(f"Total articles fetched: {len(result)}")


if __name__ == "__main__":
    asyncio.run(main())
