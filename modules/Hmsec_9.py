"""현대차증권 — 서버 모듈. scrapers/hmsec_core.py 사용."""
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.ConfigManager import config
from scrapers.hmsec_core import scrape_hmsec

def Hmsec_checkNewArticle():
    urls = config.get_urls("Hmsec_9")
    return scrape_hmsec(urls) if urls else []
