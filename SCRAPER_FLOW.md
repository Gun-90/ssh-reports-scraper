# External Reports Scraper Flow

이 문서는 **External Reports Hub의 수집 파이프라인 수집기(`ssh-reports-scraper`)**의 아키텍처 및 크롤링 작동 원리를 설명하여, 다른 LLM이 복잡한 크롤링 엔진 코드를 전부 들여다보지 않고도 핵심 동작 구조를 이해하도록 돕습니다.

---

## 1. 스크래퍼 시스템 작동 흐름도 (Scraper System Flow)

증권사 크롤링 수집기는 Cron 스케줄러(또는 주기적 루프 배치)에 의해 각 증권사의 리서치 센터 게시판을 탐색하여, 실시간으로 등록되는 신규 리포트 글을 파싱 및 중복 배제하여 공통 데이터베이스에 고속 적재합니다.

```mermaid
flowchart TD
    %% 시작 조건
    Scheduler["Cron 스케줄러 / Orchestrator\n(주기적 트리거: 예: 10분 간격)"] -->|Trigger Run| MasterScraper["scraper_orchestrator.py\n(전체 증권사 수집 총괄)"]

    %% 개별 증권사 수집 파트
    subgraph "Individual Brokerage Scrapers"
        MasterScraper --> Scraper_Mirae["mirae_asset.py\n(미래에셋증권 파서)"]
        MasterScraper --> Scraper_Shinhan["shinhan_sec.py\n(신한투자증권 파서)"]
        MasterScraper --> Scraper_KB["kb_sec.py\n(KB증권 파서)"]
        MasterScraper --> Scraper_Hana["hana_sec.py\n(하나증권 파서)"]
    end

    %% 크롤링 기법
    subgraph "Scraping Methodologies"
        Scraper_Mirae -->|HTTP JSON API Request| APIGet["Requests / httpx"]
        Scraper_Shinhan -->|HTML Parsing| BS4Parse["BeautifulSoup 4"]
        Scraper_KB -->|Dynamic Render PDF Link| SeleniumRun["Playwright / Selenium\n(Headless Browser)"]
    end

    %% 가공 및 검증 파트
    subgraph "Data Process & Validation"
        APIGet & BS4Parse & SeleniumRun --> RawData["Raw Report JSON / HTML Object"]
        RawData --> KeyGen["Generate Unique Hash Key\n(firm_nm + board_id + post_id)"]
        KeyGen --> DBCheck["Check Redundancy\n(DB 중복키 존재 여부 조회)"]
    end

    %% 최종 저장
    subgraph "Database Target"
        DBCheck -->|Not Exists| SaveDB["Insert tbl_sec_reports\n(sync_status = 0 초기 설정)"]
        DBCheck -->|Exists| SkipData["Ignore & Skip\n(중복 적재 패스)"]
    end
end
```

---

## 2. 개별 수집 대상 증권사 명세 (Target Brokerages)

시스템에 등록되어 동작 중인 주요 수집 대상 마스터 정보는 `tbm_sec_firm_info` 및 `tbm_sec_firm_board_info`를 바탕으로 하며, 각 증권사 게시판 종류(종목 분석, 산업 분석, 거시 경제 등)별로 최적화된 선택적 파서 클래스가 연동됩니다.

| 증권사 코드 | 증권사명 (firm_nm) | 주로 사용하는 수집 기법 | 비고 |
| :---: | :--- | :--- | :--- |
| `01` | 미래에셋증권 | REST API (JSON 응답 파싱) | 가장 빠른 수집 속도 |
| `02` | 신한투자증권 | BeautifulSoup 4 (HTML 정적 파싱) | 특정 클래스명 태그 파싱 |
| `03` | KB증권 | Playwright / Headless Browser | 동적 PDF 다운로드 스크립트 대응 |
| `04` | 하나증권 | BeautifulSoup 4 + 정규식 | 첨부파일 링크 정밀 추출 |
| `05` | 한국투자증권 | REST API 파싱 및 토큰 인증 우회 | 세션 우회 로직 연동 |

---

## 3. 핵심 중복 배제 메커니즘 (De-duplication Logic)

각기 다른 증권사 게시판에서 매일 수백 건의 리포트가 쏟아지기 때문에, 네트워크 통신 지연이나 스케줄러 중복 실행 상황에서도 동일한 리포트가 중복 적재되지 않도록 하는 **고유 식별자(`key`)** 설계가 탑재되어 있습니다.

```python
# key 생성 규칙 예제
unique_key = hash_md5(firm_nm + "_" + board_cd + "_" + article_id)
# 1. 수집 직후 DB에 해당 `key`가 이미 tbl_sec_reports에 등록되어 있는지 조회
# 2. 존재할 경우, 즉각 처리를 중단하고 다음 리포트 파싱 단계로 진행
```

이 규칙을 통해 중복 유입률 0%를 유지하며, DB의 고유성 제약 조건(Unique Constraint)을 안전하게 수호합니다.
