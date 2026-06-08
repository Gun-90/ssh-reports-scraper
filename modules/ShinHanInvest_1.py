# -*- coding:utf-8 -*- 
import gc
import aiohttp
import asyncio
import requests
import re
from datetime import datetime, timedelta
import os
import sys
import json
from loguru import logger
from urllib.parse import parse_qs, urlparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.FirmInfo import FirmInfo
from models.WebScraper import SyncWebScraper
from models.db_factory import get_db
from models.ConfigManager import config

def ShinHanInvest_checkNewArticle_back(cur_page=1, single_page_only=True):
    sec_firm_order = 1
    article_board_order = 0
    json_data_list = []

    requests.packages.urllib3.disable_warnings()

    if cur_page is None:
        cur_page = 1
    # 신한증권 국내산업분석
    TARGET_URL_0 = 'giindustry'
    
    # 신한증권 국내기업분석
    TARGET_URL_1 = 'gicompanyanalyst'

    # 신한증권 국내스몰캡
    TARGET_URL_2 = 'giresearchIPO'
    
    # 신한증권 해외주식
    TARGET_URL_3 = 'foreignstock'
    
    TARGET_URL_TUPLE = (TARGET_URL_0, TARGET_URL_1, TARGET_URL_2, TARGET_URL_3)

    # URL GET
    for article_board_order, TARGET_URL in enumerate(TARGET_URL_TUPLE):
        firm_info = FirmInfo(
            sec_firm_order=sec_firm_order,
            article_board_order=article_board_order
        )

        # 변동되는 파라미터 
        board_name = TARGET_URL
        param1 = "Q1"
        param2 = "+"
        param3 = ""
        param5 = "Q"
        param6 = 99999
        param7 = ""
        type_param = "bbs2"
        base_url = "https://open2.shinhaninvest.com/phone/asset/module/getbbsdata.jsp"

        while True:
            # URL 구성
            TARGET_URL = (f"{base_url}?url=/mobile/json.list.do?boardName={board_name}&curPage={cur_page}"
                f"&param1={param1}&param2={param2}&param3={param3}&param4=/mobile/json.list.do?boardName={board_name}&curPage={cur_page}"
                f"&param5={param5}&param6={param6}&param7={param7}&type={type_param}")

            scraper = SyncWebScraper(TARGET_URL, firm_info)
            
            # HTML parse
            jres = scraper.GetJson()
            # logger.debug(jres)
            logger.info(f"Calling URL: {TARGET_URL}")
            
            # title_map에서 동적으로 키 매핑
            title_map = {v: k for k, v in jres['title'].items()}  # 키-값을 역으로 매핑
            logger.info(title_map)
            reg_dt_key = title_map.get('등록일', '')  # 등록일 키
            title_key = title_map.get('제목', '')  # 제목 키
            url_key = title_map.get('파일명', '')  # 파일명 키
            

            # 작성자 또는 애널리스트 키 매핑
            writer_key = title_map.get('작성자', '') or title_map.get('애널리스트', '')  # 작성자 또는 애널리스트 키

            soupList = jres['list']
            if not soupList:
                break

            # JSON To List
            for item in soupList:
                reg_dt = item.get(reg_dt_key, '')  # 등록일
                if reg_dt:
                    reg_dt = re.sub(r"[-./]", "", reg_dt).replace(";", "")
                LIST_ARTICLE_TITLE = item.get(title_key, '')  # 제목
                LIST_ARTICLE_URL = item.get(url_key, '')  # 파일명
                writer = item.get(writer_key, '')  # 작성자

                try:
                    LIST_ARTICLE_URL = LIST_ARTICLE_URL.replace('shinhaninvest.com', 'shinhansec.com')
                    LIST_ARTICLE_URL = LIST_ARTICLE_URL.replace('/board/message/file.do?', '/board/message/file.pdf.do?')
                except Exception as e:
                    logger.error("에러 발생:", e)
                    LIST_ARTICLE_URL = item.get(url_key, '')
                
                json_data_list.append({
                    "sec_firm_order": sec_firm_order,
                    "article_board_order": article_board_order,
                    "firm_nm": firm_info.get_firm_name(),
                    "reg_dt": reg_dt,
                    "download_url": LIST_ARTICLE_URL,
                    "telegram_url": LIST_ARTICLE_URL,
                    "article_title": LIST_ARTICLE_TITLE,
                    "writer": writer,
                    "key:": LIST_ARTICLE_URL,
                    "save_time": datetime.now().isoformat()
                })

            # 다음 페이지로 이동
            if single_page_only:
                break
            cur_page += 1
        
        # 메모리 정리
        del scraper
        gc.collect()

    return json_data_list


board_map = {
    'giindustry': 0,        # 산업분석
    'gicompanyanalyst': 1,  # 기업분석
    'giresearchIPO': 2,     # 스몰캡
    'foreignstock': 3,      # 해외 주식
    'alternative': 4,       # 대체투자
    'foreignbond': 5,       # 해외 채권
    'gibond': 6,            # 채권/신용분석
    'gicomment': 7,         # 주식전략/시황
    'gieconomy': 8,         # 경제
    'gifuture': 9,          # 기술적분석/파생시황
    'gigoodpolio': 10,      # 주식 포트폴리오
    'giperiodicaldaily': 11,# Daily 신한생각
    'issuebroker': 12,      # 의무리포트
    'shinhannews': 13,      # 신한 속보
    'gistockchart': 11,     # Daily 계열
    'plananalysis': 10,     # 기획분석/포트폴리오 계열
    'fxmarket': 8,          # 경제/외환
    'commodity': 8,         # 경제/외환
    'gifund2': 4,           # 대체투자
    'giperiodicalinvestetf': 9, # ESG/퀀트/ETF
}

MOBILE_LIST_URL = "https://m.shinhansec.com/mweb/invt/shrh/ishrh1001"
MOBILE_API_URL = "https://m.shinhansec.com/mweb/api/invt/shrh/ishrhShrhList"
BBS_API_URL = "https://bbs2.shinhansec.com/mobile/json.list.do"

STR_BOARD_GROUPS = (
    "giperiodicaldaily|gistockchart|plananalysis|gicompanyanalyst|giindustry|gieconomy|fxmarket|commodity|gibond|foreignbond",
)
BBS_BOARD_NAMES = (
    "foreignstock",
    "giresearchIPO",
    "gieconomy",
    "gicomment",
    "gibond",
    "foreignbond",
    "gifuture",
    "alternative",
)
STR_PAGE_LIMIT = int(os.getenv("SHINHAN_STR_PAGE_LIMIT", "30"))
BBS_PAGE_LIMIT = int(os.getenv("SHINHAN_BBS_PAGE_LIMIT", "3"))
LOOKBACK_DAYS = int(os.getenv("SHINHAN_LOOKBACK_DAYS", "45"))


def _normalize_reg_dt(value):
    value = str(value or "").strip()
    value = re.sub(r"[^0-9]", "", value)
    return value[:8] if len(value) >= 8 else value


def _report_save_time(value):
    value = str(value or "").strip()
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) >= 14:
        return (
            f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}T"
            f"{digits[8:10]}:{digits[10:12]}:{digits[12:14]}"
        )
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}T00:00:00"
    return datetime.now().isoformat()


def _lookback_cutoff():
    return (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")


def _is_recent_reg_dt(reg_dt, cutoff):
    return bool(reg_dt) and reg_dt >= cutoff


def _normalize_pdf_url(url):
    url = str(url or "").strip()
    if not url:
        return ""
    url = url.replace("http://", "https://", 1)
    url = url.replace("shinhaninvest.com", "shinhansec.com")
    url = url.replace("/board/message/file.do?", "/board/message/file.pdf.do?")
    return url


def _extract_message_number(url):
    if not url:
        return ""
    query = parse_qs(urlparse(url).query)
    return query.get("messageNumber", [""])[0]


def _build_article(item, firm_info):
    board_name = item.get("bbs_name") or item.get("BOARD_NAME") or item.get("boardName") or ""
    raw_reg_dt = item.get("date") or item.get("reg_dt") or item.get("REG_DT") or ""
    reg_dt = _normalize_reg_dt(raw_reg_dt)
    download_url = _normalize_pdf_url(
        item.get("attachment_url") or item.get("ATTACHMENT_ID") or item.get("download_url") or ""
    )
    if item.get("ATTACHMENT_ID") and not str(item.get("ATTACHMENT_ID")).startswith("http"):
        download_url = f"https://bbs2.shinhansec.com/board/message/file.pdf.do?attachmentId={item.get('ATTACHMENT_ID')}"

    article_url = item.get("message_url") or item.get("article_url") or ""
    if not article_url and board_name:
        message_id = item.get("MESSAGE_ID") or item.get("messageId") or ""
        message_number = item.get("MESSAGE_NUMBER") or item.get("message_id") or ""
        if message_id or message_number:
            article_url = (
                f"https://bbs2.shinhansec.com/mobile/view.do?boardName={board_name}"
                f"&messageId={message_id}&messageNumber={message_number}"
            )

    if not download_url:
        return None

    return {
        "sec_firm_order": 1,
        "article_board_order": board_map.get(board_name, 99),
        "firm_nm": firm_info.get_firm_name(),
        "reg_dt": reg_dt,
        "article_url": article_url,
        "download_url": download_url,
        "telegram_url": download_url,
        "pdf_url": download_url,
        "article_title": item.get("title") or item.get("TITLE") or "",
        "writer": item.get("nickname") or item.get("REGISTER_NICKNAME") or item.get("writer") or "",
        "key": download_url,
        "save_time": _report_save_time(raw_reg_dt)
    }


def _build_bbs_item(board_name, item, title_map):
    reverse_title_map = {v: k for k, v in title_map.items()}
    title_key = reverse_title_map.get("제목", "f1")
    reg_dt_key = reverse_title_map.get("등록일", "f0")
    url_key = reverse_title_map.get("파일명", "f3")
    writer_key = reverse_title_map.get("작성자") or reverse_title_map.get("애널리스트") or "f5"
    body_key = reverse_title_map.get("본문URL") or reverse_title_map.get("본문") or "f6"

    return {
        "bbs_name": board_name,
        "date": item.get(reg_dt_key, ""),
        "title": item.get(title_key, ""),
        "nickname": item.get(writer_key, ""),
        "attachment_url": item.get(url_key, ""),
        "message_url": item.get(body_key, ""),
        "message_id": _extract_message_number(item.get(body_key, "")),
    }


async def _fetch_str_group(session, url, headers, bbs_name):
    rows = []
    repeat_key_n = ""
    cutoff = _lookback_cutoff()
    for page_no in range(STR_PAGE_LIMIT):
        data = {
            "url": "/mweb/api/invt/shrh/ishrhShrhList",
            "callbackFun": "ishrh1001.tab1_callbackFun",
            "bbs_name": bbs_name,
            "repeatKeyP": "",
            "repeatKeyN": repeat_key_n,
            "curPage": 1,
            "lastPageFlag": "true",
            "tran": False,
        }
        async with session.post(url, headers=headers, data=json.dumps(data)) as response:
            if response.status != 200:
                logger.error(f"ShinHanInvest STr request failed: {response.status}, bbs_name={bbs_name}")
                break
            result = await response.json()

        if result.get("header", {}).get("resultCode") != "00000":
            logger.warning(f"ShinHanInvest STr result error: {result.get('header')}")
            break

        item_list = result.get("body", {}).get("list01", {}).get("outputList", []) or []
        logger.info(f"ShinHanInvest STr: bbs_name={bbs_name}, page={page_no + 1}, items={len(item_list)}")
        recent_items = [
            item for item in item_list
            if _is_recent_reg_dt(_normalize_reg_dt(item.get("date")), cutoff)
        ]
        rows.extend(recent_items)

        next_key = result.get("header", {}).get("repeatKeyN", "")
        if not item_list or not next_key or next_key == repeat_key_n:
            break
        if len(recent_items) < len(item_list):
            break
        repeat_key_n = next_key
    return rows


async def _fetch_bbs_board(session, headers, board_name):
    rows = []
    cutoff = _lookback_cutoff()
    for cur_page in range(1, BBS_PAGE_LIMIT + 1):
        url = f"{BBS_API_URL}?boardName={board_name}&curPage={cur_page}"
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                logger.error(f"ShinHanInvest BBS request failed: {response.status}, board={board_name}")
                break
            text = await response.text()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"ShinHanInvest BBS JSON parse failed: {board_name}, {e}")
            break

        item_list = result.get("list", []) or []
        title_map = result.get("title", {}) or {}
        logger.info(f"ShinHanInvest BBS: board={board_name}, page={cur_page}, items={len(item_list)}")
        normalized_items = [_build_bbs_item(board_name, item, title_map) for item in item_list]
        recent_items = [
            item for item in normalized_items
            if _is_recent_reg_dt(_normalize_reg_dt(item.get("date")), cutoff)
        ]
        rows.extend(recent_items)

        if not item_list or result.get("lastPageFlag") == "true":
            break
        if len(recent_items) < len(item_list):
            break
    return rows


async def ShinHanInvest_checkNewArticle():
    sec_firm_order = 1
    json_data_list = []
    
    urls = config.get_urls("ShinHanInvest_1")
    if not urls:
        logger.warning("No URLs found for ShinHanInvest_1")
        return []
    url = urls[0]

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0",
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": MOBILE_LIST_URL,
        "Priority": "u=0",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    logger.debug(f"ShinHanInvest Scraper Start: {url}")
    firm_info = FirmInfo(sec_firm_order=sec_firm_order, article_board_order=0)
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for bbs_name in STR_BOARD_GROUPS:
            json_data_list.extend(
                _build_article(item, firm_info)
                for item in await _fetch_str_group(session, url, headers, bbs_name)
            )

        bbs_headers = dict(headers)
        bbs_headers.pop("Content-Type", None)
        for board_name in BBS_BOARD_NAMES:
            json_data_list.extend(
                _build_article(item, firm_info)
                for item in await _fetch_bbs_board(session, bbs_headers, board_name)
            )

    deduped = {}
    for item in json_data_list:
        if not item or not item.get("key"):
            continue
        deduped[item["key"]] = item

    logger.info(f"ShinHanInvest: fetched={len(json_data_list)}, unique={len(deduped)}")
    if not deduped:
        logger.warning(
            "ShinHanInvest returned 0 unique articles. "
            "Check m.shinhansec.com API payload/response shape."
        )
    return list(deduped.values())

def get_shinhan_board_info():
    """
    Fetches data from Shinhan Invest API and prints a unique list of
    BOARD_NAME and BOARD_TITLE pairs.
    """
    urls = config.get_urls("ShinHanInvest_1")
    if not urls:
        logger.warning("No URLs found for ShinHanInvest_1")
        return []
    url = urls[0]

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0",
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Priority": "u=0",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    data = {
        "header": {
            "TCD": "S",
            "SDT": datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3],
            "SVW": "/siw/insights/research/list/view-popup.do"
        },
        "body": {
            "startCount": 0,
            "listCount": 10000,
            "query": "",
            "searchType": "A",
            "boardCode": ""
        }
    }

    board_info = set()

    with requests.Session() as session:
        response = session.post(url, headers=headers, data=json.dumps(data))

        if response.ok:
            result = response.json()
            
            collectionList = result.get('body', {}).get('collectionList', [])
            for collection in collectionList:
                itemList = collection.get('itemList', [])
                for item in itemList:
                    board_name = item.get('BOARD_NAME', 'N/A')
                    board_title = item.get('BOARD_TITLE', 'N/A')
                    board_info.add((board_name, board_title))
            
            logger.info("Found Board Information:")
            for name, title in sorted(list(board_info)):
                logger.info(f'BOARD_NAME: "{name}", BOARD_TITLE: "{title}"')

        else:
            logger.info("Request failed:", response.status_code)

if __name__ == "__main__":
    firm_info = FirmInfo(sec_firm_order=1, article_board_order=0)
    # results = asyncio.run(ShinHanInvest_checkNewArticle(cur_page=1, single_page_only=True))
    results = asyncio.run(ShinHanInvest_checkNewArticle())
    # logger.debug(results)
    logger.info(f"Fetched {len(results)} articles from .", firm_info.get_firm_name())
    # logger.debug(results)

    db = get_db()
    inserted_count_results = db.insert_json_data_list(results)

    logger.info(f"Articles Inserted: {inserted_count_results}")
