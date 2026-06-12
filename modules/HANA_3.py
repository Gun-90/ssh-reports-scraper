"""하나증권 — 서버 모듈. scrapers/hana_core.py 사용."""
import asyncio,os,sys
from loguru import logger
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))
from models.ConfigManager import config
from scrapers.hana_core import scrape_hana

async def HANA_checkNewArticle(full_fetch=False):
    urls=config.get_urls("HANA_3")
    if not urls:logger.warning("No URLs for HANA_3");return[]
    loop=asyncio.get_event_loop()
    try:return await loop.run_in_executor(None,scrape_hana,urls)
    except Exception as e:logger.error(f"HANA error: {e}");return[]
