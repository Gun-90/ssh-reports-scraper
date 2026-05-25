#!/usr/bin/env python3
"""
Standalone BNK투자증권 스크래퍼 (GitHub Actions 전용)
- 의존성: aiohttp, beautifulsoup4
- FirmInfo / ConfigManager / DB 없이 독립 실행
- 결과를 JSON으로 stdout 출력
"""

import asyncio
import json
import re
import sys
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup

BNK_URLS = [
    "https://www.bnkfn.co.kr/research/analysingCompany.jspx",
    "https://www.bnkfn.co.kr/research/analysingIssue.jspx",
    "https://www.bnkfn.co.kr/research/economyAnalyse.jspx",
    "https://www.bnkfn.co.kr/research/marketOverview2.jspx",
]

HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "ko,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

BOARD_NAMES = {
    0: "기업분석",
    1: "이슈분석",
    2: "경제분석",
    3: "시장동향",
}


async def fetch_url(session: aiohttp.ClientSession, url: str, retries: int = 5) -> BeautifulSoup | None:
    """URL을 가져와서 BeautifulSoup 객체로 반환, 실패 시 None"""
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=HEADERS, timeout=20) as resp:
                resp.raise_for_status()
                html = await resp.text()
                return BeautifulSoup(html, "html.parser")
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(1 * attempt)
            else:
                print(f"[ERROR] Final failure for {url}: {e}", file=sys.stderr)
                return None


async def scrape_bnk() -> list[dict]:
    """BNK투자증권 리서치 리포트 스크래핑"""
    articles: list[dict] = []

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in BNK_URLS]
        soups = await asyncio.gather(*tasks, return_exceptions=True)

        for board_order, (soup, url) in enumerate(zip(soups, BNK_URLS)):
            if isinstance(soup, Exception) or soup is None:
                print(f"[WARN] Skipping board {board_order} ({url}): {type(soup).__name__}", file=sys.stderr)
                continue

            table = soup.find("table", class_="table01")
            if not table:
                print(f"[WARN] Table not found in {url}", file=sys.stderr)
                continue

            rows = table.select("tbody tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 6:
                    continue

                article_link = cells[1].find("a")
                writer = cells[2].get_text(strip=True)
                if not article_link:
                    continue

                article_title = article_link.get_text(strip=True)

                # onclick에서 첨부파일 URL 추출
                onclick_attr = article_link.get("onclick", "")
                match = re.search(
                    r"viewAction\(this, '\d+', '(/uploads/[^']+)', '([^']+)'\);",
                    onclick_attr,
                )
                article_url = ""
                if match:
                    base_path = match.group(1)
                    file_name = match.group(2)
                    article_url = f"https://www.bnkfn.co.kr{base_path}/{file_name}"

                reg_dt = cells[4].get_text(strip=True)

                articles.append({
                    "sec_firm_order": 23,
                    "article_board_order": board_order,
                    "board_name": BOARD_NAMES.get(board_order, f"board_{board_order}"),
                    "firm_nm": "BNK투자증권",
                    "reg_dt": re.sub(r"[-./]", "", reg_dt),
                    "article_title": article_title,
                    "article_url": article_url,
                    "download_url": article_url,
                    "telegram_url": article_url,
                    "writer": writer,
                    "save_time": datetime.now().isoformat(),
                    "key": article_url,
                })

    return articles


def main():
    print("[INFO] Starting BNK scraper on GitHub Actions...", file=sys.stderr)
    articles = asyncio.run(scrape_bnk())
    print(f"[INFO] Scraped {len(articles)} articles", file=sys.stderr)

    # 결과를 JSON으로 stdout 출력
    output = {
        "scraped_at": datetime.now().isoformat(),
        "source": "github-actions",
        "count": len(articles),
        "articles": articles,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
