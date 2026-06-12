"""미래에셋증권 — 서버 모듈. scrapers/miraeasset_core.py 사용."""
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.ConfigManager import config
from scrapers.miraeasset_core import scrape_miraeasset

def Miraeasset_checkNewArticle():
    urls = config.get_urls("Miraeasset_8")
    return scrape_miraeasset(urls) if urls else []
