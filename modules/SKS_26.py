"""SK증권 — 서버 모듈. scrapers/sks_core.py 사용."""
import os,sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))
from models.ConfigManager import config
from scrapers.sks_core import scrape_sks

def Sks_checkNewArticle():
    urls=config.get_urls("SKS_26")
    return scrape_sks(urls) if urls else []
