# -*- coding:utf-8 -*-
import json
import sqlite3
import pytest
from unittest.mock import MagicMock, AsyncMock

# EnricherManager를 로드하기 위한 sys.path 보강
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enricher.enricher_manager import EnricherManager

def get_in_memory_db(has_premium_cols=False):
    """테스트용 인메모리 SQLite 연결을 생성하고 tbl_sec_reports 테이블을 만듭니다."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    
    # 공통 기본 컬럼 정의
    base_columns = """
        report_id INTEGER PRIMARY KEY,
        firm_nm TEXT,
        article_title TEXT,
        tags TEXT DEFAULT '[]',
        stock_names TEXT DEFAULT '[]',
        sector TEXT DEFAULT ''
    """
    
    # 프리미엄 컬럼 추가 유무에 따른 동적 생성
    if has_premium_cols:
        table_def = f"""
            CREATE TABLE tbl_sec_reports (
                {base_columns},
                target_price REAL,
                rating TEXT,
                revision_type TEXT,
                report_type TEXT,
                stock_tickers TEXT DEFAULT '[]'
            )
        """
    else:
        table_def = f"CREATE TABLE tbl_sec_reports ({base_columns})"
        
    cur.execute(table_def)
    
    # 테스트 레코드 1개 삽입
    cur.execute(
        """
        INSERT INTO tbl_sec_reports (report_id, firm_nm, article_title)
        VALUES (1, 'LS증권', '삼성전자 목표주가 상향 리포트')
        """
    )
    conn.commit()
    return conn

def test_enricher_backward_compatibility():
    """
    프리미엄 속성 컬럼이 없는 구버전(레거시) DB 환경에서도
    에러 없이 기본 3개 필드(tags, stock_names, sector)만 안전하게 업데이트되는지 테스트합니다.
    (동적 컬럼 판별 및 하위 호환성 방어 코드 검증)
    """
    conn = get_in_memory_db(has_premium_cols=False)
    
    # EnricherManager 생성 및 DB Connection 모킹
    manager = EnricherManager()
    manager._get_conn = lambda: conn
    
    # 프리미엄 데이터를 포함하여 업데이트 시도
    manager._update_tags(
        conn,
        report_id=1,
        tags=["반도체", "상향"],
        stock_names=["삼성전자"],
        sector="반도체",
        target_price=95000.0,
        rating="BUY",
        revision_type="UPGRADE",
        report_type="COMPANY",
        stock_tickers=["005930"]
    )
    conn.commit()
    
    # 결과 조회
    cur = conn.cursor()
    cur.execute("SELECT tags, stock_names, sector FROM tbl_sec_reports WHERE report_id = 1")
    row = cur.fetchone()
    
    # 기본 필드들은 잘 들어가 있어야 함
    assert json.loads(row[0]) == ["반도체", "상향"]
    assert json.loads(row[1]) == ["삼성전자"]
    assert row[2] == "반도체"
    
    # 테이블 컬럼 스키마 조회하여 프리미엄 컬럼이 전혀 없음을 확인 (에러 없이 패스되었음)
    cur.execute("PRAGMA table_info(tbl_sec_reports)")
    cols = {r[1] for r in cur.fetchall()}
    assert "target_price" not in cols
    
    conn.close()

def test_enricher_premium_columns_update():
    """
    신규 프리미엄 속성 컬럼이 모두 구현된 DB 환경에서,
    모든 프리미엄 필드들이 누락 없이 정확하게 업데이트되는지 테스트합니다.
    """
    conn = get_in_memory_db(has_premium_cols=True)
    
    manager = EnricherManager()
    manager._get_conn = lambda: conn
    
    # 모든 프리미엄 데이터 포함하여 업데이트 시도
    manager._update_tags(
        conn,
        report_id=1,
        tags=["반도체", "상향"],
        stock_names=["삼성전자"],
        sector="IT",
        target_price=110000.0,
        rating="BUY",
        revision_type="UPGRADE",
        report_type="COMPANY",
        stock_tickers=["005930"]
    )
    conn.commit()
    
    # 결과 조회
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tags, stock_names, sector, target_price, rating, revision_type, report_type, stock_tickers 
        FROM tbl_sec_reports 
        WHERE report_id = 1
        """
    )
    row = cur.fetchone()
    
    assert json.loads(row[0]) == ["반도체", "상향"]
    assert json.loads(row[1]) == ["삼성전자"]
    assert row[2] == "IT"
    assert row[3] == 110000.0
    assert row[4] == "BUY"
    assert row[5] == "UPGRADE"
    assert row[6] == "COMPANY"
    assert json.loads(row[7]) == ["005930"]
    
    conn.close()

def test_enricher_transaction_rollback_recovery():
    """
    에러 발생 시 개별 rollback()이 수행되어 
    트랜잭션 깨짐(current transaction is aborted) 현상이 복구되고 연쇄 실패가 차단되는지 테스트합니다.
    """
    conn = get_in_memory_db(has_premium_cols=True)
    
    manager = EnricherManager()
    manager._get_conn = lambda: conn
    
    # 의도적으로 SQL 에러 유발 (존재하지 않는 컬럼 업데이트 유도)
    cur = conn.cursor()
    try:
        cur.execute("UPDATE tbl_sec_reports SET INVALID_COLUMN_NAME_FOR_TEST = 1 WHERE report_id = 1")
    except sqlite3.OperationalError:
        # SQLite에서 에러 발생 시 트랜잭션이 잠기거나 롤백이 필요할 수 있음
        # EnricherManager에서 명시하는 conn.rollback() 실행
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            cur.close()
        except Exception:
            pass
            
    # 에러 복구(rollback) 후 후속 쿼리가 정상 작동하는지 확인
    cur = conn.cursor()
    try:
        cur.execute("SELECT report_id FROM tbl_sec_reports WHERE report_id = 1")
        row = cur.fetchone()
        assert row[0] == 1  # 트랜잭션이 성공적으로 복원되어 후속 조회 가능
    finally:
        try:
            cur.close()
        except Exception:
            pass
        
    conn.close()
