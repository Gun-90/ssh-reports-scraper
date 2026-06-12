# -*- coding:utf-8 -*-
"""삼성증권 — 서버 모듈. scrapers/samsung_core.py 사용."""
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.ConfigManager import config
from scrapers.samsung_core import scrape_samsung


def Samsung_checkNewArticle():
    urls = config.get_urls("Samsung_5")
    if not urls:
        return []
    return scrape_samsung(urls)
