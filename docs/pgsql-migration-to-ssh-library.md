# PostgreSQL 통신 클래스 → ssh-library 마이그레이션

## 목표

현재 `ssh-reports-scraper` 프로젝트 내 `models/PostgreSQLManager.py`에 구현된 PostgreSQL 통신 로직을
서버 공통 라이브러리 `~/lib/ssh-library/`의 `SecReportsManager`로 이전한다.

## 2026-06-03 진행 기준

- 관리자 화면에서 DB의 최신 저장일자를 이미 확인하고 있으므로, 별도 scheduler heartbeat보다 DB 공통화 작업을 먼저 진행한다.
- 사이드이펙트를 줄이기 위해 scraper 런타임 전환은 뒤로 미룬다.
- 이번 우선순위는 Phase 0~1이다.
  - Phase 0: `ssh-library` import 가능 상태 확인 및 path dependency 준비
  - Phase 1: 현재 `PostgreSQLManager`와 호환되는 `SecReportsManager` API를 library에 먼저 추가
- Phase 2(`db_factory` 전환)는 read-only smoke test와 주요 메서드 parity 확인 후 별도 커밋으로 진행한다.

## 배경

| 항목 | 현재 위치 | 목적지 |
|------|-----------|--------|
| 기본 연결/쿼리 | `models/PostgreSQLManager.py` (자체 구현) | `ssh_library.database.BasePostgreSQLManager` |
| reports CRUD + 스크래핑 파이프라인 | `models/PostgreSQLManager.py` | `ssh_library.reports.SecReportsManager` |
| 팩토리 함수 | `models/db_factory.get_db()` | 유지 (반환 타입만 변경) |

## Phase 0 — 공유 라이브러리 설치

**변경 파일**: `pyproject.toml` 1개  
**리스크**: 없음 (설치만 하고 코드 변경 없음)

- `ssh-reports-scraper`의 의존성에 `ssh-library`를 path dependency로 추가
- `uv sync` 또는 `uv pip install -e ~/workspace/lib/ssh-library`로 설치

**상태:** 보류. `pyproject.toml`에 로컬 path dependency를 바로 추가하면 GitHub Actions runner에서 `~/workspace/lib/ssh-library` 경로가 없어질 수 있다. Phase 2 전환 전에 git dependency 또는 배포 서버 path 보장 방식 중 하나를 선택한다.

## Phase 1 — 공유 라이브러리에 메서드 이전

**변경 파일**: `~/workspace/lib/ssh-library/src/ssh_library/reports.py` 1개
**리스크**: 없음 (현재 프로젝트 코드 변경 없음)

- 현재 `PostgreSQLManager`에만 있는 메서드들을 `SecReportsManager` 클래스로 복사
- API(`_fetchall`, `_execute`, 시그니처) 완전 동일 유지
- 테이블명 참조: `self.main_table_name` → `self.table_name`으로 통일

**상태:** 완료. `~/workspace/lib/ssh-library/src/ssh_library/reports.py`에 scraper 호환 API를 보강했다. scraper의 `models/db_factory.py`는 아직 전환하지 않는다.

### 2026-06-03 Phase 1 보강 내용

- `SecReportsManager._last_inserted_keys` 추가
- `insert_json_data_list()`가 빈 목록에서 `(0, 0)`을 반환하도록 보정
- `insert_json_data_list()`가 `RETURNING key, inserted`를 사용해 신규 key를 추적하도록 보정
- `update_report_tags()` 추가
- `fetch_pending_tag_reports()` 추가
- keyword table 이름을 현재 scraper 구현과 맞춰 `tbl_sec_reports_alert_keywords`로 정정
- library 단위 테스트 추가 및 `uv run pytest -q tests` 통과

### 이전 대상 메서드 목록

| # | 메서드 | 비고 |
|---|--------|------|
| 1 | `MAIN_TABLE`, `_TABLE_MAP` 상수 | 테이블명 매핑 |
| 2 | `insert_json_data_list` | 배치 upsert (extras.execute_values) |
| 3 | `fetch_daily_articles_by_date` | async, 텔레그램 미발송 데이터 조회 |
| 4 | `fetch_all_empty_telegram_url_articles` | async |
| 5 | `fetch_ls_detail_targets` | async |
| 6 | `update_telegram_url` | async |
| 7 | `daily_select_data` | async, 발송/다운로드 대상 |
| 8 | `daily_update_data` | async, 발송/다운로드 완료 처리 |
| 9 | `update_report_summary_by_telegram_url` | async, gemini 요약 |
| 10 | `update_report_summary` | async |
| 11 | `fetch_pending_summary_reports` | async |
| 12 | `fetch_existing_keys` | 동기, 중복 방지용 |
| 13 | `reset_send_status` | async |
| 14 | `execute_query` | async, SQLite 호환 레이어 |
| 15 | `load_keywords_from_db` | 키워드 알림 |
| 16 | `fetch_keyword_reports` | 키워드 매칭 |
| 17 | `update_keyword_send_user` | 발송 기록 |

## Phase 2 — `db_factory` 전환 (주요 전환점)

**변경 파일**: `models/db_factory.py` 1개  
**리스크**: 중간. 문제 시 `db_factory.py`만 롤백하면 복구 가능

- `get_db()`가 `PostgreSQLManager` 대신 `SecReportsManager`를 반환
- 모든 소비 코드(`scraper.py`, 모듈들, run 스크립트)는 변경 없음
- 배포 후 `daily_send_report`, `keyword_alert` 등 주요 기능 smoke test

### 롤백 절차
```bash
git checkout models/db_factory.py
# 또는 이전 버전으로 복원
```

## Phase 3 — 점진적 직접 임포트 전환 (선택사항)

**리스크**: 낮음. 개별 파일 단위로 진행

- 필요시 개별 파일에서 `from ssh_library import SecReportsManager` 직접 사용
- `db_factory.get_db()` 호출과 혼용 가능 (동일 인터페이스)

## Phase 4 — 로컬 `PostgreSQLManager.py` 제거

**리스크**: 없음. 단, 모든 참조가 사라진 후에만 진행

- `models/PostgreSQLManager.py`, `models/db_factory.py` 제거
- `git grep PostgreSQLManager`로 미처리 참조 없는지 확인

## 검증 방법

각 Phase 후 아래를 확인한다:

```bash
# Phase 0: 임포트 가능 확인
cd ~/prod/ssh-reports-scraper
python3 -c "from ssh_library import SecReportsManager; print('OK')"

# Phase 2: 실제 DB 연결 테스트 (read-only)
python3 -c "
from models.db_factory import get_db
db = get_db()
rows = db._fetchall('SELECT 1 AS test')
print('Connection OK:', rows)
"
```

## 타임라인

| Phase | 작업 | 예상 시간 | 담당 |
|-------|------|-----------|------|
| 0 | 설치 | 5분 | — |
| 1 | 메서드 이전 | 30분 | — |
| 2 | db_factory 전환 + 테스트 | 30분 | 주말 작업 |
| 3 | 직접 임포트 (선택) | 필요시 | — |
| 4 | 정리 | 10분 | — |
