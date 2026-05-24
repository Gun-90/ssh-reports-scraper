--
-- Migration: 레포트 태그/종목명/산업 컬럼 추가
-- tbl_sec_reports 테이블에 검색 강화를 위한 구조화된 메타데이터 컬럼 추가
--

-- PostgreSQL JSONB 컬럼 추가
ALTER TABLE public.tbl_sec_reports
  ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS stock_names JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS sector TEXT DEFAULT '';

-- tags 컬럼 GIN 인덱스 (JSONB 배열 검색 최적화)
CREATE INDEX IF NOT EXISTS idx_tb_sec_reports_tags ON public.tbl_sec_reports USING gin (tags);

-- stock_names 컬럼 GIN 인덱스
CREATE INDEX IF NOT EXISTS idx_tb_sec_reports_stock_names ON public.tbl_sec_reports USING gin (stock_names);

-- sector 컬럼 B-tree 인덱스
CREATE INDEX IF NOT EXISTS idx_tb_sec_reports_sector ON public.tbl_sec_reports USING btree (sector);

COMMENT ON COLUMN public.tbl_sec_reports.tags IS 'LLM 추출 태그 배열 (예: ["반도체", "목표주가상향", "실적전망"])';
COMMENT ON COLUMN public.tbl_sec_reports.stock_names IS 'LLM 추출 종목명 배열 (예: ["삼성전자", "SK하이닉스"])';
COMMENT ON COLUMN public.tbl_sec_reports.sector IS 'LLM 추출 산업분류 (예: 반도체, 바이오, 금융)';
