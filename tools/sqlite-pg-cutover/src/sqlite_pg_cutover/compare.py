from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import psycopg

from .schema import Table, quote_ident


@dataclass(frozen=True)
class CompareResult:
    table: str
    sqlite_count: int
    postgres_count: int | None
    count_matches: bool
    sample_matches: bool | None
    note: str = ""


def compare_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn: psycopg.Connection,
    table: Table,
    *,
    sample_size: int = 20,
) -> CompareResult:
    sqlite_count = table.row_count
    try:
        with pg_conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table.pg_name}"')
            pg_count = int(cur.fetchone()[0])
    except Exception as exc:
        return CompareResult(table.name, sqlite_count, None, False, None, f"PostgreSQL count failed: {exc}")

    sample_matches = None
    note = ""
    if table.primary_key_columns and table.columns and sample_size > 0:
        pk = table.primary_key_columns[0]
        source_cols = [c.name for c in table.columns]
        pg_cols = [c.pg_name for c in table.columns]
        sqlite_rows = sqlite_conn.execute(
            f"SELECT {', '.join(quote_ident(c) for c in source_cols)} FROM {quote_ident(table.name)} "
            f"ORDER BY {quote_ident(pk.name)} LIMIT ?",
            (sample_size,),
        ).fetchall()
        sample_matches = True
        with pg_conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            for row in sqlite_rows:
                cur.execute(
                    f'SELECT {", ".join(quote_ident(c) for c in pg_cols)} FROM "{table.pg_name}" '
                    f'WHERE "{pk.pg_name}" = %s',
                    (row[pk.name],),
                )
                pg_row = cur.fetchone()
                if pg_row is None:
                    sample_matches = False
                    note = f"Sample missing primary key {pk.name}={row[pk.name]!r}"
                    break
                for src, dst in zip(source_cols, pg_cols):
                    if str(row[src] or "") != str(pg_row[dst] or ""):
                        sample_matches = False
                        note = f"Sample mismatch on {src} for primary key {pk.name}={row[pk.name]!r}"
                        break
                if sample_matches is False:
                    break

    return CompareResult(
        table=table.name,
        sqlite_count=sqlite_count,
        postgres_count=pg_count,
        count_matches=sqlite_count == pg_count,
        sample_matches=sample_matches,
        note=note,
    )
