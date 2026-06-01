# Refactoring & Improvement Roadmap

> **Session**: 2026-05-31 ~ 2026-06-01  
> **Context**: 증권사 스크래퍼 GitHub Actions 이관 시도, URL 보안 정리, 프론트 건강검진 탭 추가  
> **Goal**: LLM/개발자 실수 포인트 파악 → 개선 과제 도출

---

## 1. LLM 실수 패턴 분석

### 1.1 Module-level side effects (치명적)

**문제**: `_D = config.get_base_url("KEY")` 같은 모듈 레벨 코드가 `from models.ConfigManager import config` 보다 먼저 실행되어 `NameError` 발생.

**근본 원인**: Python 모듈 import 순서에 의존하는 전역 변수 선언. LLM은 파일 전체 맥락을 읽지 않고 패턴 매칭으로 코드 삽입.

**16개 모듈 장애** (프로덕션 2시간 중단)

```python
# ❌ LLM이 생성한 코드 (import 전에 config 참조)
from models.FirmInfo import FirmInfo
_D = config.get_base_url("ShinHanInvest_1")  # NameError!
...
from models.ConfigManager import config

# ✅ 올바른 순서
from models.ConfigManager import config
from models.FirmInfo import FirmInfo
_D = config.get_base_url("ShinHanInvest_1")
```

### 1.2 Batch patching without validation

**문제**: `sed`/Python 스크립트로 27개 파일 일괄 수정 후 문법 검증 없이 배포.

**영향**: `f-string` 내 `{config.get_base_url(...)}` 구문 오류로 10개 모듈 추가 장애.

**LLM 특성**: 속도 중시 → 검증 생략. 사람 개발자라면 한 파일씩 테스트했을 것.

### 1.3 Production context blindness

**문제**: GitHub Actions 환경에 `secrets.json`이 없고 `tbm_sec_firm_info` SQLite 테이블도 없는데, 이를 모르고 GA 이관 강행.

**영향**: GA workflow 3회 연속 실패 (`FirmInfo Error`, `No URLs found`, `0 articles`).

**LLM 특성**: 서버 환경(ssh oci)과 GA 환경 차이를 추론하지 못함.

### 1.4 Cross-repo confusion

**문제**:  
- `ssh-reports-scraper` (Python, 단독 repo, submodule)  
- `ssh-management-hub-fastAPI` (Python, internal.management-hub repo, Docker)  
- `ssh-reports-hub` (React frontend, Netlify, submodule)  

**영향**: `/admin/firm-health` 엔드포인트를 reports-hub FastAPI에 추가했다가 management-hub로 재배포. 3개 repo 사이를 오가며 컨텍스트 스위칭 비용 큼.

### 1.5 URL secrecy inconsistency

**문제**:  
- `config/urls.json`을 git에 커밋했다가 API 경로 노출로 삭제  
- `secrets.json` 방식으로 전환했지만 27개 모듈에 하드코딩 도메인이 남아있음  

**LLM 특성**: "숨겨야 할 것"과 "공개해도 되는 것" 구분 불명확.

---

## 2. 코드 구조 문제점

### 2.1 ConfigManager — 단일 실패점

```python
# 현재: secrets.json 없으면 빈 배열 반환 → 모든 스크래퍼 0건
def get_urls(self, key, default=None):
    return self._secrets.get("urls", {}).get(key, [])
```

**문제**: secrets.json 로드 실패 시 명확한 에러 대신 silent failure.

### 2.2 FirmInfo — DB 의존성

```python
# SQLite/PostgreSQL 없으면 FirmInfo._firm_data = {}
# 모든 증권사 이름이 "Unknown(N)"으로 표시됨
```

**문제**: GitHub Actions 등 DB 없는 환경에서 scrapers는 작동하지만 메타데이터 누락.

### 2.3 모듈 간 import 순서 의존성

20개 모듈이 `from models.ConfigManager import config`를 서로 다른 위치에서 import. 모듈 레벨 변수(`_D`, `_D2`)가 import 순서에 의존.

### 2.4 Monorepo submodule 관리

```
external.reports-hub (root)
├── apps/scrapers/ssh-reports-scraper  ← git submodule
├── apps/frontend/ssh-reports-hub      ← git submodule
└── apps/backend/ssh-reports-hub-fastAPI ← git submodule

internal.management-hub (root)
└── apps/backend/ssh-management-hub-fastAPI ← 별도 repo
```

**문제**: 한 기능이 프론트+백엔드+스크래퍼 3~4개 repo에 걸침.

---

## 3. 개선 과제 (우선순위 순)

### 🔴 P0 — 당장 필요

| # | 과제 | 파일 | 비고 |
|---|------|------|------|
| 1 | **ConfigManager URL fallback 개선** | `models/ConfigManager.py` | secrets.json 없을 때 `ValueError` raise 하도록 변경 (silent failure 방지) |
| 2 | **FirmInfo 하드코딩 fallback 추가** | `models/FirmInfo.py` | DB 없을 때 기본 firm_names 리스트 내장 (GA/dry-run 지원) |
| 3 | **LS_0.py URL 리팩토링** | `modules/LS_0.py` | `msg.ls-sec.co.kr`, `nls-sec.co.kr` 등 하드코딩 도메인 → secrets.json config로 이동 |
| 4 | **standalone_ls_scraper BOARD_URLS** | `scripts/standalone_ls_scraper.py` | 10개 하드코딩 URL → `config.get_urls("LS_0")` 로 교체 |

### 🟡 P1 — 안정성 개선

| # | 과제 | 파일 | 비고 |
|---|------|------|------|
| 5 | **모듈 import 순서 표준화** | 전체 `modules/*.py` | `config`, `FirmInfo` import를 항상 최상단에 배치하는 lint 규칙 |
| 6 | **pre-commit hook: URL leak detector** | `.pre-commit-config.yaml` | `https?://` 패턴 커밋 시 경고/차단 (secrets.json 경로 제외) |
| 7 | **CI 파이프라인: 모듈 import test** | `.github/workflows/test.yml` | `python -c "from modules.X import checkNewArticle"` 전 모듈 검증 |
| 8 | **scheduler health endpoint** | `scheduler.py` | `/health` 엔드포인트 또는 Telegram 알람 (scraper 실패 시 즉시 통보) |
| 9 | **증권사 scraper 개별 타임아웃** | `scraper.py` | LS처럼 오래 걸리는 scraper가 전체를 blocking하지 않도록 분리 |

### 🟢 P2 — 개발 경험

| # | 과제 | 파일 | 비고 |
|---|------|------|------|
| 10 | **frontend: CSS module 전환** | `src/*.css` | Inline style + global CSS 혼재 → CSS Module 또는 Tailwind로 통일 |
| 11 | **API base URL 환경변수화** | `src/constants/config.js` | `https://ssh-oci.duckdns.org` 하드코딩 → `VITE_API_BASE_URL` |
| 12 | **DB migration 스크립트 정리** | `scripts/` | `koreainvestment_backfill.py`, `toss_backfill.py`, `heungkuk_backfill.py` 통합 |
| 13 | **monorepo: Makefile/task 통합** | root `Makefile` | 서브모듈 pull/build/deploy 한 번에 실행 |

---

## 4. LLM 안전 가드 제안

| 원칙 | 설명 |
|------|------|
| **No batch patching** | 한 번에 3개 이상 파일 수정 금지. 반드시 파일별 commit + syntax check |
| **Test before push** | `python -m py_compile` + `import` 체크를 커밋 전 필수 수행 |
| **Production guard** | 프로덕션 코드 수정 전 `git diff --stat` 확인 후 사용자 승인 |
| **Domain list** | 수정 가능한 도메인 화이트리스트 제공 → 이외 도메인 발견 시 확인 |

---

## 5. 현재 git 상태

```
external.reports-hub/apps/scrapers/ssh-reports-scraper  → main (90c61d0 + URL comment fixes)
external.reports-hub/apps/frontend/ssh-reports-hub      → main (health tab + text-select)
internal.management-hub/.../ssh-management-hub-fastAPI   → 서버 직접 패치 (firm-health endpoint)
```

**주의**: management-hub의 `firm-health` 엔드포인트가 git에 커밋되지 않은 상태. 서버 `/tmp/patch_mgmt.py` 로만 적용됨 → 별도 커밋 필요.
