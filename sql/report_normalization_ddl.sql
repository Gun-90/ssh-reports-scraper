--
-- tbl_sec_reports 정규화 — 관심사별 4개 테이블 분리
-- 2026-06-11
--
-- 네이밍 룰:
--   tbl_ = 쌓이는 데이터 (레코드)
--   tbm_ = 마스터/기준정보 (소량, 참조용)

-- 1) Enricher 태그/종목 데이터 (title 기반 규칙 추출, AI 아님)
CREATE TABLE IF NOT EXISTS tbl_report_enricher_tags (
    report_id bigint PRIMARY KEY REFERENCES tbl_sec_reports(report_id) ON DELETE CASCADE,
    tags jsonb DEFAULT '[]'::jsonb,       -- LLM이 추출한 키워드 태그
    stock_names jsonb DEFAULT '[]'::jsonb, -- LLM이 추출한 종목명
    stock_tickers jsonb DEFAULT '[]'::jsonb, -- LLM이 추출한 티커
    sector text DEFAULT '',               -- LLM이 추출한 산업분류
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 2) LLM 요약 데이터
CREATE TABLE IF NOT EXISTS tbl_report_ai_summaries (
    report_id bigint PRIMARY KEY REFERENCES tbl_sec_reports(report_id) ON DELETE CASCADE,
    gemini_summary text,                  -- LLM 3줄 요약
    summary_time text,                    -- 요약 생성 시각
    summary_model text,                   -- 사용된 LLM 모델명
    created_at timestamptz DEFAULT now()
);

-- 3) 목표주가/투자의견 (FnGuide 매칭 포함)
CREATE TABLE IF NOT EXISTS tbl_report_price_targets (
    report_id bigint PRIMARY KEY REFERENCES tbl_sec_reports(report_id) ON DELETE CASCADE,
    target_price numeric,                 -- 목표주가
    rating text,                          -- 투자의견 (Buy/Hold/Sell)
    revision_type text,                   -- 리비전 유형 (상향/하향/유지)
    report_type text,                     -- 리포트 유형
    fnguide_summary_id bigint,            -- FnGuide 요약 매칭 FK
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_targets_fnguide ON tbl_report_price_targets(fnguide_summary_id);

-- 4) PDF 다운로드/처리 상태 → pdf-archiver가 tbl_sec_reports + tbl_sec_reports_pdf_archive에서 전담.
--    별도 테이블 불필요. 2026-06-11 확인 후 DROP.

-- 데이터 마이그레이션 (기존 tbl_sec_reports → 신규 테이블)
INSERT INTO tbl_report_enricher_tags (report_id, tags, stock_names, stock_tickers, sector)
SELECT report_id, tags, stock_names, stock_tickers, sector
FROM tbl_sec_reports
WHERE NOT (tags IS NULL AND stock_names IS NULL AND stock_tickers IS NULL AND sector IS NULL)
ON CONFLICT (report_id) DO NOTHING;

INSERT INTO tbl_report_ai_summaries (report_id, gemini_summary, summary_time, summary_model)
SELECT report_id, gemini_summary, summary_time, summary_model
FROM tbl_sec_reports
WHERE gemini_summary IS NOT NULL AND gemini_summary != ''
ON CONFLICT (report_id) DO NOTHING;

INSERT INTO tbl_report_price_targets (report_id, target_price, rating, revision_type, report_type, fnguide_summary_id)
SELECT report_id, target_price, rating, revision_type, report_type, fnguide_summary_id
FROM tbl_sec_reports
WHERE NOT (target_price IS NULL AND rating IS NULL AND fnguide_summary_id IS NULL)
ON CONFLICT (report_id) DO NOTHING;

-- tbl_report_downloads: pdf-archiver가 tbl_sec_reports + tbl_sec_reports_pdf_archive에서 전담 → 테이블 불필요 (2026-06-11 DROP 완료)
