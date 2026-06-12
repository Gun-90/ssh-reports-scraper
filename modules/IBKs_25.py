"""IBK투자증권 — 서버 모듈. scrapers/ibk_core.py 사용."""
import asyncio, os, sys
from loguru import logger
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.ConfigManager import config
from scrapers.ibk_core import scrape_ibk

BOARDS = [
    {"name":"전략/시황","url":None,"screen":"IKO010101","path":"invreport"},
    {"name":"기업분석","url":None,"screen":"IKO010201","path":"busreport"},
    {"name":"산업분석","url":None,"screen":"IKO010301","path":"indreport"},
    {"name":"경제/채권","url":None,"screen":"IKO010401","path":"comment"},
    {"name":"해외기업분석","url":None,"screen":"IKO010501","path":"overseasreport","menu_tp":"0"},
    {"name":"글로벌ETF","url":None,"screen":"IKO010501","path":"overseasreport","menu_tp":"1"},
]

async def IBK_checkNewArticle(page=1, board_idx=None, full_fetch=False):
    urls = config.get_urls("IBKs_25")
    if not urls or len(urls) < 6:
        logger.warning("No URLs for IBKs_25")
        return []
    boards = [{**b, "url": urls[i]} for i, b in enumerate(BOARDS)]
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, scrape_ibk, boards)
    except Exception as e:
        logger.error(f"IBK error: {e}")
        return []
