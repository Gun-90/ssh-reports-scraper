#!/usr/bin/env python3
"""
통합 리포트 PDF URL 후처리 스크립트

실행:  uv run run/fix_all_db.py              ← 방향키↑↓ + 스페이스 토글 + 엔터확정
       uv run run/fix_all_db.py all          ← 전체 (nohup 용)
       uv run run/fix_all_db.py meritz       ← 메리츠만
       uv run run/fix_all_db.py ls           ← LS만
       uv run run/fix_all_db.py yuanta,hmsec ← 유안타+현대차
"""
import asyncio
import os
import sys
import time
import termios
import tty
from datetime import datetime
from loguru import logger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ── 각 증권사 fix 함수 ────────────────────────────────────────────────────────

def _import_ls_fix():
    os.environ["LS_SEARCH_DAYS"] = "5"
    from run.fix_ls_db import fix_ls_urls
    return fix_ls_urls


def _import_meritz_fix():
    from run.fix_meritz_db import fix_meritz_urls
    return fix_meritz_urls


def _import_ibk_fix():
    from run.fix_ibk_db import fix_ibk_urls
    return fix_ibk_urls


def _import_daeshin_fix():
    from run.fix_daeshin_db import fix_daeshin_urls
    return fix_daeshin_urls


def _import_dbfi_fix():
    from run.fix_dbfi_urls import fix_dbfi_urls
    return fix_dbfi_urls


def _import_yuanta_fix():
    from run.fix_yuanta_db import fix_yuanta_urls
    return fix_yuanta_urls


def _import_hmsec_fix():
    from run.fix_hmsec_db import fix_hmsec_urls
    return fix_hmsec_urls


def _import_im_fix():
    from run.fix_im_db import fix_im_urls
    return fix_im_urls


def _import_kyobo_fix():
    from run.fix_kyobo_db import fix_kyobo_urls
    return fix_kyobo_urls


def _import_sks_fix():
    from run.fix_sks_db import fix_sks_urls
    return fix_sks_urls


FIRM_FIXES = [
    ("ls",      _import_ls_fix,     "upload/ fallback → msg. 정적 URL"),
    ("meritz",  _import_meritz_fix, "article_url 재방문 → WorkFlow URL"),
    ("ibk",     _import_ibk_fix,    "게시판별 path 보정 → download.ibks.com"),
    ("daeshin", _import_daeshin_fix,"PDF URL HEAD 검증 + HTTP→HTTPS"),
    ("dbfi",    _import_dbfi_fix,   "key URL 재방문 → gate URL 복구"),
    ("yuanta",  _import_yuanta_fix, "HTTP→HTTPS 변환 + article 재추출"),
    ("hmsec",   _import_hmsec_fix,  "SynapDocViewer URL → 직접 PDF URL"),
    ("im",      _import_im_fix,     "upload/ URL HEAD 검증"),
    ("kyobo",   _import_kyobo_fix,  "upload/ URL HEAD 검증"),
    ("sks",     _import_sks_fix,    "PDF URL HEAD 검증"),
]
FIRM_LABELS = {
    "ls": "LS증권", "meritz": "메리츠증권", "ibk": "IBK투자증권",
    "daeshin": "대신증권", "dbfi": "DB증권",
    "yuanta": "유안타증권", "hmsec": "현대차증권",
    "im": "IM증권", "kyobo": "교보증권", "sks": "SK증권",
}


# ── 키 입력 (cbreak 모드 — 방향키/스페이스/엔터 지원) ───────────────────────

def _get_key() -> str:
    """한 글자 or 방향키 시퀀스를 읽어서 키 식별 문자열 반환"""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        b0 = sys.stdin.buffer.read(1)
        if b0 == b"\x1b":
            b1 = sys.stdin.buffer.read(1)
            if b1 == b"[":
                b2 = sys.stdin.buffer.read(1)
                if b2 == b"A":
                    return "UP"
                if b2 == b"B":
                    return "DOWN"
            return "ESC"
        if b0 == b" ":
            return "SPACE"
        if b0 == b"\x03":
            return "CTRL_C"
        if b0 in (b"\n", b"\r"):
            return "ENTER"
        return b0.decode("utf-8", errors="replace")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── 실시간 토글 선택 ────────────────────────────────────────────────────────

def select_firms() -> list[str]:
    """방향키(↑↓) 이동 + 스페이스바 토글 + 엔터 확정"""

    # ── CLI 인자 ──
    if len(sys.argv) > 1:
        raw = sys.argv[1].lower()
        if raw == "all":
            return [k for k, _, _ in FIRM_FIXES]
        firms = [f.strip() for f in raw.split(",") if f.strip() in [k for k, _, _ in FIRM_FIXES]]
        if firms:
            return firms

    selected = {k: False for k, _, _ in FIRM_FIXES}  # 초기값: 전체 해제
    cursor = 0

    def render():
        lines = [""]
        lines.append("=" * 56)
        lines.append("  리포트 PDF URL 후처리 — 실행할 증권사 선택")
        lines.append("=" * 56)
        for i, (key, _, desc) in enumerate(FIRM_FIXES):
            mark = "●" if selected[key] else "○"
            label = FIRM_LABELS[key]
            pointer = " ▸" if i == cursor else "  "
            lines.append(f"{pointer} {mark}  {label:12s} — {desc}")
        lines.append("─" * 56)
        names = ", ".join(FIRM_LABELS[k] for k in selected if selected[k])
        lines.append(f"  선택: {names}" if names else "  선택: 없음")
        lines.append("  [↑↓] 이동  [스페이스] 토글  [엔터] 확정  [q] 종료")
        lines.append("=" * 56)
        return "\n".join(lines)

    # ── 첫 렌더는 현재 위치에 그냥 출력, 이후는 위로 올려 덮어쓰기 ──
    _menu_lines = 0

    def redraw(output: str, first: bool = False):
        nonlocal _menu_lines
        if first:
            sys.stdout.write(output)
            # 18줄 → \n 17개 → 위로 17칸 이동해야 제자리
            _menu_lines = output.count("\n")
        else:
            sys.stdout.write(f"\033[{_menu_lines}A\033[J{output}")
        sys.stdout.flush()

    redraw(render(), first=True)

    while True:
        key = _get_key()

        if key == "ENTER":
            break
        if key in ("q", "Q", "CTRL_C"):
            print("\n")
            return []

        if key == "UP":
            if cursor > 0:
                cursor -= 1
            redraw(render())
        elif key == "DOWN":
            if cursor < len(FIRM_FIXES) - 1:
                cursor += 1
            redraw(render())
        elif key == "SPACE":
            firm_key = FIRM_FIXES[cursor][0]
            selected[firm_key] = not selected[firm_key]
            redraw(render())

    result = [k for k, v in selected.items() if v]
    if not result:
        print("\n  → 선택 없음. 종료합니다.\n")
        return []
    names = ", ".join(FIRM_LABELS[s] for s in result)
    print(f"\n  → 실행: {names}\n")
    return result


# ── 실행 ──────────────────────────────────────────────────────────────────────

async def run_selected(firms: list[str]):
    if not firms:
        logger.info("선택된 증권사가 없어 종료합니다.")
        return

    logger.info("=" * 60)
    logger.info("통합 리포트 PDF URL 후처리 시작")
    logger.info(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    log_names = [FIRM_LABELS.get(f, f) for f in firms]
    logger.info(f"실행 대상 ({len(firms)}개): {', '.join(log_names)}")

    total_start = time.time()
    results = {}

    for firm_key in firms:
        found = [x for x in FIRM_FIXES if x[0] == firm_key]
        if not found:
            continue

        _, import_fn, description = found[0]
        fix_func = import_fn()
        firm_label = FIRM_LABELS.get(firm_key, firm_key)

        logger.info("")
        logger.info("─" * 50)
        logger.info(f"[{firm_label}] 처리 시작 — {description}")
        logger.info("─" * 50)

        firm_start = time.time()
        try:
            await fix_func()
            elapsed = time.time() - firm_start
            results[firm_key] = {"status": "성공", "elapsed": elapsed}
            logger.success(f"[{firm_label}] 처리 완료 (소요: {elapsed:.1f}초)")
        except Exception as e:
            elapsed = time.time() - firm_start
            results[firm_key] = {"status": f"실패: {e}", "elapsed": elapsed}
            logger.error(f"[{firm_label}] 처리 중 오류: {e}")

        await asyncio.sleep(2)

    total_elapsed = time.time() - total_start
    logger.info("")
    logger.info("=" * 60)
    logger.info("통합 후처리 최종 결과 요약")
    logger.info("=" * 60)
    for firm_key, result in results.items():
        label = FIRM_LABELS.get(firm_key, firm_key)
        logger.info(f"  {label:12s} | {result['status']} ({result['elapsed']:.1f}초)")
    logger.info("─" * 60)
    logger.info(f"  총 소요 시간: {total_elapsed:.1f}초")
    logger.info("=" * 60)


if __name__ == "__main__":
    firms = select_firms()

    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "fix_all_db.log")

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")
    logger.add(log_file, level="DEBUG",
               rotation="10 MB", retention="30 days", encoding="utf-8",
               format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}")

    asyncio.run(run_selected(firms))
