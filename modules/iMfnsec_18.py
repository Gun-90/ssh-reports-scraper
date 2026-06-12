"""IM증권 — 서버 모듈. scrapers/imfn_core.py 사용."""
import asyncio,os,sys
from loguru import logger
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))
from models.ConfigManager import config
from scrapers.imfn_core import scrape_imfn

async def iMfnsec_checkNewArticle(cur_page="1",single_page_only=True):
    urls=config.get_urls("iMfnsec_18")
    if not urls:logger.warning("No URLs for iMfnsec_18");return[]
    loop=asyncio.get_event_loop()
    try:return await loop.run_in_executor(None,scrape_imfn,urls[0])
    except Exception as e:logger.error(f"iMfn error: {e}");return[]
