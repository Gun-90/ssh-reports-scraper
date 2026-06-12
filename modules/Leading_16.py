# -*- coding:utf-8 -*-
"""리딩투자증권 — 서버 모듈 (scraper.py fallback).
공통 코어 scrapers/leading_core.py 사용 → GA standalone과 로직 통일."""
import asyncio
import os
import sys

from loguru import logger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.ConfigManager import config
from scrapers.leading_core import scrape_leading


async def Leading_checkNewArticle():
    urls = config.get_urls("Leading_16")
    if not urls:
        logger.warning("No URLs found for Leading_16")
        return []

    logger.debug("Leading Scraper Start: 리딩투자증권 via scrapers.leading_core")

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, scrape_leading, urls)
        logger.info(f"Leading Scraper: Found {len(result)} articles")
        return result
    except Exception as e:
        logger.error(f"Error scraping Leading: {e}")
        return []


async def main():
    result = await Leading_checkNewArticle()
    logger.info(f"Total articles fetched: {len(result)}")


if __name__ == "__main__":
    asyncio.run(main())
