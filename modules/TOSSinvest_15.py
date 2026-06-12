# -*- coding:utf-8 -*-
"""토스증권 — 서버 모듈. scrapers/toss_core.py 사용."""
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.ConfigManager import config
from scrapers.toss_core import scrape_toss


def TOSSinvest_checkNewArticle():
    urls = config.get_urls("TOSSinvest_15")
    if not urls:
        return []
    return scrape_toss(urls)
