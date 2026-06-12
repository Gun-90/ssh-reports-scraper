# -*- coding:utf-8 -*-
"""흥국증권 — 서버 모듈. scrapers/heungkuk_core.py 사용."""
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.ConfigManager import config
from scrapers.heungkuk_core import scrape_heungkuk


def Heungkuk_checkNewArticle():
    urls = config.get_urls("Heungkuk_28")
    if not urls:
        return []
    return scrape_heungkuk(urls)
