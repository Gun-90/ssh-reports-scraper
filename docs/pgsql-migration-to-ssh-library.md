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

**상태:** 부분 진행. `DB_BACKEND=ssh_library` opt-in 경로를 추가해 로컬/서버에서 `SecReportsManager` smoke test를 할 수 있게 했다. 기본 운영값(`DB_BACKEND=postgres`)은 아직 기존 `models.PostgreSQLManager`를 반환한다.

### 2026-06-03 Phase 2 opt-in 내용

- `models/db_factory.py`에 `DB_BACKEND=ssh_library` 분기 추가
- `ssh_library.SecReportsManager`가 import 가능할 때만 사용
- Docker/GitHub Actions 이미지에는 아직 `ssh-library`를 포함하지 않음
- `tests/test_db_factory.py`로 기본 backend와 opt-in backend를 검증
- `make test-imports`에 db factory test 추가

### 2026-06-03 read-only smoke 결과

아래 두 경로 모두 같은 DB에 read-only query가 성공했다.

- 기존 경로: `models.PostgreSQLManager`
- opt-in 경로: `DB_BACKEND=ssh_library` + `ssh_library.SecReportsManager`

검증 쿼리:

```sql
SELECT COUNT(*)::int AS count, MAX(save_time)::text AS latest_save_time
FROM tbl_sec_reports;
```

결과는 두 경로 모두 동일했다.

```text
count=283061
latest_save_time=2026-06-02T18:54:46.000610
```

### Phase 2 남은 결정

- private `ssh-library`를 Docker image에 넣는 방식 결정
  - 후보 A: GitHub Actions에서 `ssh-library`를 checkout한 뒤 Docker build context에 포함
  - 후보 B: GHCR base image 또는 wheel artifact로 배포
  - 후보 C: repo를 public/package로 전환 후 git/PyPI dependency 사용
- 이미지에 library가 포함된 뒤에만 운영 `DB_BACKEND`를 `ssh_library`로 변경

### 2026-06-03 Docker image 포함 방식

추천안 A를 적용했다.

```text
GitHub Actions
  ├─ checkout ssh-reports-scraper
  ├─ mkdir vendor/ssh-library
  ├─ SSH_LIBRARY_DEPLOY_KEY가 있으면 private ssh-library checkout
  └─ docker buildx build
       ├─ context=.
       ├─ build-context ssh_library=./vendor/ssh-library
       └─ build-arg INSTALL_SSH_LIBRARY=1 또는 0
```

Dockerfile은 BuildKit named context를 사용한다.

```text
RUN --mount=from=ssh_library,target=/tmp/ssh-library
```

- `INSTALL_SSH_LIBRARY=1`: `/tmp/ssh-library`를 현재 project venv에 설치
- `INSTALL_SSH_LIBRARY=0`: 설치를 건너뛰고 기존 이미지 빌드 유지

필요한 GitHub secret:

- `SSH_LIBRARY_DEPLOY_KEY`: `liante0904/ssh-library` private repo를 읽을 수 있는 deploy key 또는 SSH private key

2026-06-03 상태:

- `liante0904/ssh-library`에 read-only deploy key `ssh-reports-scraper-ci-readonly` 등록 완료
- `liante0904/ssh-reports-scraper` Actions secret `SSH_LIBRARY_DEPLOY_KEY` 등록 완료

주의:

- 이 단계는 image에 library를 넣을 수 있게 한 준비 작업이다.
- 운영 `.env`의 `DB_BACKEND`는 아직 `postgres`로 둔다.
- `DB_BACKEND=ssh_library` 전환은 이미지 안에서 `python -c "from ssh_library import SecReportsManager"` smoke가 성공한 뒤 진행한다.

### 롤백 절차
```bash
DB_BACKEND=postgres
# 또는 git revert <db_factory 전환 커밋>
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
