"""FirmInfo 함수형 wrapper — LLM/신규개발자용 단순 인터페이스.

기존 FirmInfo 메타클래스는 그대로 두고, 외부에서 호출하기 쉬운
일반 함수만 제공. 신규 모듈/GA standalone에서 FirmInfo 대신 이것만 import하면 됨.

사용법:
    from models.firm_utils import firm_name, board_name

    name = firm_name(4)          # → "KB증권"
    board = board_name(4, 0)     # → "기업분석"
"""
from models.FirmInfo import FirmInfo


def firm_name(sec_firm_order: int) -> str:
    """증권사명 반환. 예: firm_name(4) → 'KB증권'"""
    return FirmInfo(sec_firm_order, 0).get_firm_name()


def board_name(sec_firm_order: int, article_board_order: int = 0) -> str:
    """게시판명 반환. 예: board_name(4, 7) → 'Global Insights'"""
    return FirmInfo(sec_firm_order, article_board_order).get_board_name()


def all_firm_names() -> list[str]:
    """전체 증권사명 리스트 (sec_firm_order 순)."""
    return FirmInfo.firm_names


def telegram_update_required(sec_firm_order: int) -> bool:
    """텔레그램 발송 필요 여부."""
    return FirmInfo(sec_firm_order, 0).telegram_update_required
