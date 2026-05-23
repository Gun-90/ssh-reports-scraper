# Secrets / Env Standardization TODO

> 목적: 다음 LLM/개발자가 `~/workspace` 프로젝트들의 secrets/env 구조를 끊기지 않고 이어서 정리할 수 있게 현재 상태, 문제, 결정, 작업 순서를 기록한다.
> 작성일: 2026-05-23

## 현재 결론

큰 방향은 유지한다.

- 원본 시크릿은 Git 밖 `~/secrets/**/secrets.json`에 둔다.
- 프로젝트별 실행용 `.env`는 `~/secrets/generate_env.py`가 생성한다.
- 배포 전처리는 가능하면 `~/secrets/deploy_prepare.py`로 통일한다.

다만 지금은 **경로 기반 신형 구조**와 **앱 이름 기반 구형 문서/Makefile**이 섞여 있다. 그래서 사람/LLM이 잘못된 명령을 실행하기 쉽고, 실제로 `python3 ~/secrets/generate_env.py scraper`는 실패했다.

## 확인된 현행 동작

`~/secrets/generate_env.py`는 현재 아래처럼 동작한다.

```bash
python3 ~/secrets/generate_env.py /abs/project/path
python3 ~/secrets/generate_env.py .
```

내부 규칙:

- `project_dir`의 절대경로를 구한다.
- `rel_path = os.path.relpath(project_dir, HOME)`를 만든다.
- 우선 `~/secrets/{rel_path}/secrets.json`을 찾는다.
- 없으면 레거시 fallback으로 `~/secrets/{basename(project_dir)}/secrets.json`을 찾는다.
- `.env`를 `project_dir/.env`에 쓴다.
- 현재는 `.env` 생성 후 무조건 `docker image prune -f`도 실행한다.

문제 예시:

```bash
python3 ~/secrets/generate_env.py scraper
```

위 명령은 `scraper`를 경로로 해석해서 아래를 찾다가 실패한다.

```text
~/secrets/workspace/.../ssh-reports-scraper/scraper/secrets.json
```

## 주요 문제

1. 문서/Makefile과 실제 스크립트 인터페이스가 다르다.
   - `README.md`, `CLAUDE.md`, 일부 `Makefile`은 `generate_env.py scraper`, `private-hub`, `management-hub` 같은 alias를 안내한다.
   - 현행 스크립트는 alias를 지원하지 않고 경로만 지원한다.

2. `.env` 생성과 Docker image prune이 한 함수에 섞여 있다.
   - CI/LLM/개발자가 `.env`만 만들려 해도 Docker 정리가 같이 실행된다.
   - 안전한 기본 동작이 아니다.

3. CI/CD 패턴이 프로젝트마다 다르다.
   - 비교적 좋은 패턴: `deploy_prepare.py --dir ... --repo ... --sha ...`
   - `ssh-reports-scraper`는 현재 deploy workflow에서 `deploy_prepare.py`를 쓰지 않고, 서버에서 `git reset` 후 `docker compose pull/up`만 한다.
   - 즉 배포 시 `.env` 재생성이 보장되지 않는다.

4. 문서가 LLM에게 혼선을 준다.
   - `CLAUDE.md`/`README.md`의 “항상 `generate_env.py scraper`” 지침은 현재 실제 동작과 다르다.
   - 새 LLM은 문서를 믿고 실패 명령을 실행할 가능성이 높다.

## 권장 표준 명령

앞으로 문서/Makefile/LLM 지침은 아래를 표준으로 삼는 것이 가장 단순하다.

```bash
python3 ~/secrets/generate_env.py "$PWD"
```

또는 절대경로:

```bash
python3 ~/secrets/generate_env.py /home/ubuntu/workspace/external.reports-hub/apps/scrapers/ssh-reports-scraper
```

alias는 호환성 목적으로만 지원한다.

## 작업 순서

### 1. `~/secrets/generate_env.py` 개선

수정 위치:

```text
/home/ubuntu/secrets/generate_env.py
```

권장 변경:

- 인자 없으면 현재 디렉터리 기준으로 `.env` 생성:

```bash
python3 ~/secrets/generate_env.py
```

- 경로 인자는 계속 지원:

```bash
python3 ~/secrets/generate_env.py "$PWD"
```

- 기존 문서/Makefile 호환을 위해 alias 지원:

```text
scraper -> /home/ubuntu/workspace/external.reports-hub/apps/scrapers/ssh-reports-scraper
private-hub -> /home/ubuntu/workspace/internal.private-hub/apps/backend/ssh-private-hub-fastAPI
reports-hub -> /home/ubuntu/workspace/external.reports-hub/apps/backend/ssh-reports-hub-fastAPI
management-hub -> /home/ubuntu/workspace/internal.management-hub/apps/backend/ssh-management-hub-fastAPI
dart-scraper -> /home/ubuntu/prod/dart-scraper-bot 또는 실제 workspace 경로 확인 후 등록
earnings-bot -> /home/ubuntu/workspace/internal.private-hub/apps/scrapers/kr-earnings-revision-bot
fnguide-report-summary-bot -> 해당 앱 경로
```

- `docker image prune -f`는 기본 실행하지 말고 옵션으로 분리:

```bash
python3 ~/secrets/generate_env.py "$PWD" --prune
```

- dry-run/검증 옵션이 있으면 좋다:

```bash
python3 ~/secrets/generate_env.py "$PWD" --check
```

`--check`는 `.env`를 쓰지 않고 어떤 `secrets.json`을 사용할지만 출력하면 충분하다.

검증:

```bash
python3 ~/secrets/generate_env.py "$PWD" --check
python3 ~/secrets/generate_env.py "$PWD"
python3 ~/secrets/generate_env.py scraper --check
```

### 2. `deploy_prepare.py` 확인 및 유지

수정 위치:

```text
/home/ubuntu/secrets/deploy_prepare.py
```

현재 역할은 괜찮다.

- repo 준비
- `git fetch`
- `git reset --hard <sha>`
- `generate_env.generate_for_path(project_dir)` 호출

다만 `generate_env.py`에서 prune을 기본 제거하면 deploy 후 prune이 필요한 workflow는 workflow에서 명시적으로 실행하게 둔다.

### 3. `ssh-reports-scraper` deploy workflow 정리

수정 위치:

```text
.github/workflows/deploy.yml
```

현재는 배포 서버에서 직접:

```bash
cd "$DEPLOY_DIR"
git fetch origin main
git reset --hard "$EXPECTED_SHA"
docker compose pull main-scraper
docker compose up -d --no-build --force-recreate main-scraper
```

권장 변경:

```bash
python3 ~/secrets/deploy_prepare.py \
  --dir  "$DEPLOY_DIR" \
  --repo "git@github.com:${REPO_OWNER}/${REPO_NAME}.git" \
  --sha  "$EXPECTED_SHA" \
  --app  "reports-scraper"
```

주의:

- 현재 workflow에는 `REPO_NAME`, `REPO_OWNER` env가 없다. 추가 필요.
- `PROJECT_DIR` fallback 로직은 유지해도 된다.
- `deploy_prepare.py`가 `.env`를 재생성하므로 `docker compose up` 전에 env가 최신이 된다.

검증:

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"
git diff --check
```

### 4. Makefile 정리

수정 후보:

```text
/home/ubuntu/workspace/external.reports-hub/apps/scrapers/ssh-reports-scraper/Makefile
/home/ubuntu/workspace/external.reports-hub/apps/backend/ssh-reports-hub-fastAPI/Makefile
/home/ubuntu/workspace/internal.private-hub/apps/backend/ssh-private-hub-fastAPI/Makefile
/home/ubuntu/workspace/internal.management-hub/apps/backend/ssh-management-hub-fastAPI/Makefile
/home/ubuntu/workspace/internal.private-hub/apps/scrapers/kr-earnings-revision-bot/Makefile
```

권장 패턴:

```make
SECRETS := python3 $(HOME)/secrets/generate_env.py $(CURDIR)

env:
	$(SECRETS)
```

서비스 alias가 꼭 필요하면 스크립트 alias 호환을 먼저 구현한 뒤 유지한다.

### 5. 문서 정리

수정 후보:

```text
CLAUDE.md
README.md
docs/architecture.md
```

`ssh-reports-scraper` 안에서는 최소한 아래 문구로 통일:

```bash
python3 ~/secrets/generate_env.py "$PWD"
```

그리고 LLM용 규칙:

- `.env` 직접 수정 금지
- 원본은 `~/secrets/**/secrets.json`
- `.env` 재생성은 `python3 ~/secrets/generate_env.py "$PWD"`
- 배포 전처리는 `deploy_prepare.py` 사용

### 6. 전체 grep 검증

문서/Makefile 정리 후 아래 명령으로 구형 지침이 남았는지 확인:

```bash
rg -n "generate_env.py (scraper|private-hub|management-hub|earnings-bot|api)|python3 ~/secrets/generate_env.py$" \
  /home/ubuntu/workspace \
  --glob '!**/node_modules/**'
```

구형 alias를 완전히 없앨지, alias 호환을 남기고 문서만 보정할지는 선택 가능하다.

## CI/CD 현황 메모

`deploy_prepare.py`를 이미 쓰는 workflow:

- `internal.private-hub/apps/backend/ssh-private-hub-fastAPI/.github/workflows/deploy.yml`
- `internal.private-hub/apps/scrapers/dart-scraper-bot/.github/workflows/deploy.yml`
- `internal.private-hub/apps/scrapers/fear-greed-index-scraper/.github/workflows/deploy.yml`
- `internal.private-hub/apps/scrapers/kr-earnings-revision-bot/.github/workflows/deploy.yml`
- `external.reports-hub/apps/backend/ssh-reports-hub-fastAPI/.github/workflows/deploy.yml`
- `internal.management-hub/apps/backend/ssh-management-hub-fastAPI/.github/workflows/deploy.yml`

별도 방식이라 정리 우선순위가 높은 workflow:

- `external.reports-hub/apps/scrapers/ssh-reports-scraper/.github/workflows/deploy.yml`
- `internal.private-hub/apps/scrapers/fnguide-report-summary-bot/.github/workflows/deploy.yml`

## 주의사항

- `~/secrets` 아래 파일은 Git repo 밖이다. 수정 후 별도 백업/권한 관리가 필요하다.
- `.env`는 Git에 올리지 않는다.
- `generate_env.py` 수정은 여러 프로젝트에 영향이 있다. alias 추가는 backward-compatible하게 해야 한다.
- Docker prune 기본 제거는 안전하지만, 기존 deploy가 prune에 기대고 있으면 workflow 끝에서 `docker image prune -f`를 명시적으로 유지한다.

## 현재 관련 최근 작업 상태

직전 완료 작업:

- 신한 스크래퍼 API 복구
- 신한 누락분 450건 DB 백필
- 스크래퍼 0건/오래된 최신일자 health error 처리
- `origin/main` push 완료

관련 커밋:

```text
14a4351 fix: restore Shinhan scraper and fail on empty scraper results
```

