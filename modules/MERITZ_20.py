"""메리츠증권 — 서버 모듈. scrapers/meritz_core.py 사용."""
import asyncio,os,sys
from loguru import logger
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))
from models.ConfigManager import config
from scrapers.meritz_core import scrape_meritz

async def MERITZ_checkNewArticle(full_fetch=False):
    urls=config.get_urls("MERITZ_20")
    if not urls:logger.warning("No URLs for MERITZ_20");return[]
    loop=asyncio.get_event_loop()
    try:return await loop.run_in_executor(None,scrape_meritz,urls)
    except Exception as e:logger.error(f"MERITZ error: {e}");return[]
