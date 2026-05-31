import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from models.db_factory import get_db

db = get_db()
conn = db.get_connection()
cur = conn.cursor()
cur.execute("""
    SELECT sec_firm_order, firm_nm, COUNT(*) as total,
           MAX(reg_dt) as last_reg_dt, MAX(save_time::date) as last_save
    FROM tbl_sec_reports WHERE sec_firm_order IS NOT NULL
    GROUP BY sec_firm_order, firm_nm ORDER BY sec_firm_order
""")
print(f"{'ord':>3} {'firm':<22} {'total':>7} {'last_reg_dt':>12} {'last_save':>12} status")
for r in cur.fetchall():
    last = str(r[2] or "-")
    stale = "STALE!" if last < "20260501" else ("old" if last < "20260524" else "OK  ")
    print(f"{r[0]:>3} {str(r[1] or '?'):<22} {r[3]:>7} {last:>12} {str(r[4] or '-'):>12} {stale}")
conn.close()
