from __future__ import annotations

import psycopg


def connect_postgres(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn)


def table_exists(conn: psycopg.Connection, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (table_name,))
        return cur.fetchone()[0] is not None


def row_count(conn: psycopg.Connection, table_name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        return int(cur.fetchone()[0])
