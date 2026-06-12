--
-- tbm_analyst_master 시딩 — tbl_sec_reports.writer 기반
-- 2026-06-11
--
-- 증권사 리포트 작성자(writer) 컬럼에서 고유 애널리스트 추출 → 마스터 테이블에 등록
-- "리서치센터", "투자전략팀" 같은 팀명도 포함됨 → 추후 analyst_type(individual/team) 구분 예정

INSERT INTO tbm_analyst_master (name, firm)
SELECT DISTINCT writer, firm_nm
FROM tbl_sec_reports
WHERE writer IS NOT NULL
  AND writer != ''
  AND writer != 'Unknown'
  AND writer != 'N/A'
ON CONFLICT (name, firm) DO NOTHING;

-- 검증: 애널리스트별 리포트 건수 Top 10
SELECT am.name, am.firm, count(*) as report_count
FROM tbm_analyst_master am
JOIN tbl_sec_reports r ON r.writer = am.name AND r.firm_nm = am.firm
GROUP BY am.name, am.firm
ORDER BY report_count DESC
LIMIT 10;
