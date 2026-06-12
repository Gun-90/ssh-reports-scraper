"""유안타증권 — 서버 모듈. scrapers/yuanta_core.py 사용."""
import asyncio, os, sys
from loguru import logger
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.ConfigManager import config
from scrapers.yuanta_core import scrape_yuanta

async def Yuanta_checkNewArticle(is_imported_flag=False):
    urls = config.get_urls("Yuanta_27")
    if not urls:
        logger.warning("No URLs for Yuanta_27")
        return []
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, scrape_yuanta, urls[0])
    except Exception as e:
        logger.error(f"Yuanta error: {e}")
        return []
