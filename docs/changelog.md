# 프로젝트 변천사

> `master` 브랜치 원본 히스토리 + `main` 현재 코드 기반으로 재구성한 기술 변천 기록.

---

## 운영 변경 기록

### 2026-05-27 — Scraper Health Check 긴급 대응 (DBfi, BNK, TOSS)

- **DBfi 도메인 마이그레이션**: DB금융투자 API 도메인이 `m.db-fi.com` → `m.dbsec.co.kr`로 변경됨.
  - `secrets.json`의 `DBfi_19.base_url`을 새 도메인으로 업데이트.
  - `aiohttp` POST 요청이 302 redirect를 자동 추적하지 않아 빈 응답 → 0건 수집 버그 발생했었음.
  - 기존 DB 키(old domain) ↔ 신규 키(new domain) 정규화 로직 추가로 중복 삽입 방지.
- **BNKfn WARP 프록시 지원**: `www.bnkfn.co.kr`이 스크래퍼 서버에서 TCP unreachable → SOCKS5 WARP 프록시 경유로 우회.
  - `BNKfn_23.py`를 `aiohttp` 기반에서 `requests` + SOCKS5 프록시(직접→WARP fallback)로 재작성.
  - 에러 로깅 레벨 `DEBUG`(무음) → `ERROR`로 상향. 0건 수집 시 명시적 경고 출력.
- **TOSSinvest stale 임계값 오버라이드**: TOSSinvest는 게시 주기가 느려(최신 2026-05-11) 기본 5일 임계값에 걸려 health check 실패.
  - `SCRAPER_STALE_OVERRIDES` 환경변수 도입 → 모듈별 stale day 임계값 지정 가능.
  - `TOSSinvest_checkNewArticle=30`으로 설정 (30일까지 허용).
- `SCRAPER_STALE_OVERRIDES` 파싱 로직을 `scraper.py`에 추가, `log_scraper_health`에서 모듈별 오버라이드 적용.

### 2026-05-25~26 — Enricher 통합 + BNK Actions + 배포 경로 정비

- **Enricher 엔진 통합**: `insert` 완료 후 자동 태그/섹터 추출 파이프라인 추가 (`enricher/` 패키지).
  - 고속 동기식 backfill + 유휴시간(20시~06시) 대량 배치로 약 30K건/5분 처리.
  - PostgreSQL 락 경합 해소: `FOR UPDATE SKIP LOCKED` → `ORDER BY report_id` → 개별 `try/except` 순차 최적화.
- **GitHub Actions BNK 스크래퍼**: IP 차단 우회를 위한 standalone BNK 스크래퍼 Actions workflow 추가.
- **배포 경로 이전**: `~/prod/` → `~/workspace/external.reports-hub/apps/backend/`로 이전, `deploy.yml` fallback 경로 수정 및 `APP_ENV` 기본값 `dev→prod`.
- **테이블명 정규화**: `tbm_sec_reports_alert_keywords` → `tbl_sec_reports_alert_keywords`로 통일.
- **Enricher tags/sector 모듈 revert**: 별도 레포로 분리 예정.

### 2026-04-28 — PostgreSQL 스키마 소문자 정규화 및 V2 통합

- **PostgreSQL 스키마 소문자 표준화**: PostgreSQL의 기본 동작(unquoted identifier = lowercase)에 맞춰 모든 테이블명과 컬럼명을 소문자로 전환했습니다.
  - `TB_SEC_REPORTS` → `tbl_sec_reports`
  - `SEC_FIRM_ORDER`, `ARTICLE_TITLE` 등 대문자 컬럼 → `sec_firm_order`, `article_title` 등 소문자로 일괄 변경
  - SQL 파일(`sql/*.sql`)에서 모든 큰따옴표(`"`) 제거 및 제약 조건 이름 소문자화 완료
- **V2 검증본 통합 및 정리**: 검증용으로 운영하던 `docs/postgresql-v2.md`와 관련 V2 코드를 메인 라인으로 통합하고 가이드 문서를 삭제했습니다.
- **키워드 알림 로직 개선**:
  - 키워드 DB 연결 정보(`POSTGRES_KEYWORD_DB`)가 없을 경우 메인 DB를 기본값으로 사용하도록 안정화했습니다.
  - 테이블 존재 여부 체크 로직에서 커서 에러 방지 코드를 추가했습니다.
- **DBfi URL 처리 강화**: `secrets.json`의 키 구조 변화에 맞춰 `fix_dbfi_urls.py` 및 스케줄러 로직을 동기화했습니다.
- **환경변수 생성 규칙 고정**: 워크스페이스 `.env`는 프로젝트 루트에서 `python3 ~/secrets/generate_env.py` 또는 `make env`로 재생성하도록 문서화했습니다. `scraper` alias는 호환용으로만 유지합니다.
- **URL/아카이브 정리**: `ATTACH_URL`, `ARCHIVE_PATH`, `retry_count` 등에 대한 코드 참조를 정리하고, 메시지 링크 우선순위를 `TELEGRAM_URL` 중심으로 통일했습니다.

### 2026-04-26 — ATTACH_URL 전수 제거 및 LS 로직 강화 완료

- **URL 컬럼 정규화 완료**: 전체 28개 증권사 스크래퍼 모듈 및 `PostgreSQLManager`, `SQLiteManager`에서 `ATTACH_URL` 참조를 전면 제거했습니다.
- **데이터 검증**: 주의 대상(LS, 신한, 메리츠 등) 전수 조사 결과 고유 데이터 손실 0건을 확인하고 마이그레이션 종료를 선언했습니다.
- **LS증권 PDF 획득률 개선**: `msg.ls-sec.co.kr` 서버의 날짜 탐색 범위를 기존 +/- 2일에서 **+/- 10일**로 확대하여 정적 PDF 링크 확보 성공률을 극대화했습니다.
- **Fallback URL 복구 자동화**: `run/fix_ls_db.py`를 통해 기존 `upload/` 방식의 Fallback URL들을 정적 URL로 일괄 복구하는 프로세스를 가동했습니다.
- **스키마 관리 체계화**: 실제 운영 중인 PostgreSQL DB에서 테이블별 DDL을 추출하여 `sql/*.sql` 파일로 최신화하여 관리하기 시작했습니다.
- `docs/url-semantics.md` 문서를 생성하여 정규화된 URL 규약을 고정했습니다.
- `modules/ShinHanInvest_1.py` 리팩토링 시 누락되었던 모바일 뷰 전용 `ARTICLE_URL` 생성 로직을 추가했습니다.
- **DBfi endpoint 외부화**: DBfi 전용 endpoint 조합을 `secrets.json`으로 이관하고 관련 히스토리 정리했습니다.

### 2026-04-21 — PostgreSQL 재전환

- `scripts/sync_recent_sqlite_to_postgres.py`를 추가해 최근 SQLite 데이터를 JSON으로 export한 뒤 PostgreSQL `tbl_sec_reports`에 `KEY` 기준 upsert하고 정합성을 비교할 수 있게 했습니다.
- 운영 DB backend를 `DB_BACKEND=postgres`로 재전환했습니다.
- `PostgreSQLManager.execute_query()`를 추가해 기존 `SQLiteManager` 기반 DB 테스트와 동일한 인터페이스를 지원합니다.
- architecture 문서를 2026-04-21 PostgreSQL 재전환 상태와 검증 커맨드 기준으로 갱신했습니다.
... (후략) ...
