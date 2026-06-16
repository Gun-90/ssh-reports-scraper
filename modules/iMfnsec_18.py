import asyncio
import json
import re
import base64
import time
import os
import sys
from datetime import datetime
from loguru import logger

import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.FirmInfo import FirmInfo
from models.ConfigManager import config

# iMfnsec(IM증권)는 데이터센터 IP를 차단(2026-06경)하고 "입력값을 확인하세요" 페이지를
# 반환하므로 WARP SOCKS5 프록시를 경유해야 한다. 또한 board_list 요청은 invest 폼의
# 전체 필드 + 매 호출마다 새로 등록한 secureKey를 함께 보내야 한다.
BASE_URL = config.get_urls("iMfnsec_18")[0]
SOCKS_PROXY = os.getenv("SOCKS_PROXY_URL", "socks5h://localhost:9091")
PROXIES = {"http": SOCKS_PROXY, "https": SOCKS_PROXY}
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")
BIDS = ["R_E08", "R_E09", "R_E14", "R_E03", "R_E04", "R_E05"]
SEC_FIRM_ORDER = 18
NUM_PAGE = "30"
# secureKey는 세션 내에서 짧은 시간 재사용 가능하므로 보드당 1회만 등록해
# board_list + 모든 attach 호출에 재사용한다(180건 개별 등록 시 타임아웃 초과 방지).


def _headers(bid):
    return {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        "Referer": f"{BASE_URL}/mobile/invest/invest02.jsp?bid={bid}&isSmartHi=N",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE_URL,
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }


def _register_secure_key(session, headers):
    """브라우저 _setSecurityKey()와 동일: 매 source.jsp 호출 직전 새 키를 등록한다."""
    sk = base64.b64encode(f"sJS{int(time.time() * 1000)}".encode()).decode()
    try:
        session.post(f"{BASE_URL}/inc/common/PrivateSecuerKey.jsp",
                     data={"_secureKey": sk}, headers=headers, timeout=20)
    except Exception as e:
        logger.error(f"iMfnsec secureKey 등록 실패: {e}")
    return sk


def _fetch_attach_url(session, headers, bid, aid, sk):
    data = {"bid": bid, "aid": aid, "tr_cd": "db/research/twbbacl_attach", "secureKey": sk}
    try:
        r = session.post(f"{BASE_URL}/_json/source.jsp", data=data, headers=headers, timeout=20)
        a = json.loads(r.text)[0][0]
        return f"{BASE_URL}/upload/{a['file_dir']}/{a['file_name']}"
    except Exception:
        return None


def _scrape_sync():
    out = []
    for board_order, bid in enumerate(BIDS):
        firm_info = FirmInfo(sec_firm_order=SEC_FIRM_ORDER, article_board_order=board_order)
        headers = _headers(bid)
        session = requests.Session()
        session.proxies = PROXIES
        try:
            # 1) 세션 워밍업 (JSESSIONID 확립)
            session.get(f"{BASE_URL}/mobile/invest/invest02.jsp?bid={bid}&isSmartHi=N",
                        headers={"User-Agent": UA}, timeout=20)
            # 2) secureKey 등록 후 board_list (전체 폼 페이로드)
            sk = _register_secure_key(session, headers)
            data = {
                "tr_cd": "db/board/TWBBACL/board_list", "aid": "", "bid": bid,
                "cur_page": "1", "num_page": NUM_PAGE, "condition": "", "keyOption": "",
                "iKey": "", "sdate": "20240101", "edate": "", "dnURL": "/upload/",
                "iKey_view": "", "secureKey": sk,
            }
            r = session.post(f"{BASE_URL}/_json/source.jsp", data=data, headers=headers, timeout=20)
            arr = json.loads(r.text)
            items = arr[0] if arr else []
            logger.info(f"IMfnsec Scraper: bid {bid} → {len(items)} articles")
            for item in items:
                try:
                    aid = item.get("aid")
                    item_bid = item.get("bid", bid)
                    pdf_url = _fetch_attach_url(session, headers, item_bid, aid, sk)
                    out.append({
                        "sec_firm_order": SEC_FIRM_ORDER,
                        "article_board_order": board_order,
                        "firm_nm": firm_info.get_firm_name(),
                        "reg_dt": re.sub(r"[-./]", "", item.get("reg_dt", "")),
                        "article_url": BASE_URL,
                        "download_url": pdf_url,
                        "telegram_url": pdf_url,
                        "pdf_url": pdf_url,
                        "article_title": item.get("title"),
                        "writer": item.get("username"),
                        "key": pdf_url or f"{item_bid}_{aid}",
                        "save_time": datetime.now().isoformat(),
                    })
                except Exception as e:
                    logger.error(f"IMfnsec item 처리 실패 (bid {bid}): {e}")
        except Exception as e:
            logger.error(f"Error during IMfnsec scraping (bid {bid}): {e}")
        finally:
            session.close()
        time.sleep(0.3)
    return out


async def iMfnsec_checkNewArticle(cur_page="1", single_page_only=True):
    """IM증권 리서치 게시판 신규 글 수집. 동기 requests 로직을 스레드에서 실행."""
    return await asyncio.to_thread(_scrape_sync)
