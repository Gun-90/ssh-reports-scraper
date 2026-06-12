from __future__ import annotations

import sqlite3
from collections.abc import Iterable

import psycopg

from .schema import Table, quote_ident


def _clean(value):
    if isinstance(value, str):
        return value.replace("\x00", "")
    return value


def _batched(cursor: sqlite3.Cursor, size: int):
    while True:
        rows = cursor.fetchmany(size)
        if not rows:
            break
        yield rows


def copy_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn: psycopg.Connection,
    table: Table,
    *,
    batch_size: int = 1000,
    overwrite: bool = False,
) -> tuple[int, int]:
    source_cols = [c.name for c in table.columns]
    target_cols = [c.pg_name for c in table.columns]
    quoted_source_cols = ", ".join(quote_ident(c) for c in source_cols)
    quoted_target_cols = ", ".join(quote_ident(c) for c in target_cols)
    placeholders = ", ".join(["%s"] * len(target_cols))

    pk_cols = table.primary_key_columns
    conflict = ""
    if pk_cols:
        conflict_cols = ", ".join(quote_ident(c.pg_name) for c in pk_cols)
        if overwrite:
            assignments = ", ".join(
                f"{quote_ident(c.pg_name)} = EXCLUDED.{quote_ident(c.pg_name)}"
                for c in table.columns
                if c not in pk_cols
            )
            conflict = f" ON CONFLICT ({conflict_cols}) DO UPDATE SET {assignments}" if assignments else f" ON CONFLICT ({conflict_cols}) DO NOTHING"
        else:
            conflict = f" ON CONFLICT ({conflict_cols}) DO NOTHING"

    insert_sql = f'INSERT INTO "{table.pg_name}" ({quoted_target_cols}) VALUES ({placeholders}){conflict}'
    select_sql = f"SELECT {quoted_source_cols} FROM {quote_ident(table.name)}"

    inserted_or_attempted = 0
    source_cursor = sqlite_conn.execute(select_sql)
    with pg_conn.cursor() as pg_cursor:
        for rows in _batched(source_cursor, batch_size):
            values = [tuple(_clean(row[col]) for col in source_cols) for row in rows]
            pg_cursor.executemany(insert_sql, values)
            inserted_or_attempted += len(values)
        pg_conn.commit()
    return inserted_or_attempted, table.row_count


def copy_tables(
    sqlite_conn: sqlite3.Connection,
    pg_conn: psycopg.Connection,
    tables: Iterable[Table],
    *,
    batch_size: int = 1000,
    overwrite: bool = False,
) -> dict[str, tuple[int, int]]:
    result = {}
    for table in tables:
        result[table.name] = copy_table(
            sqlite_conn,
            pg_conn,
            table,
            batch_size=batch_size,
            overwrite=overwrite,
        )
    return result
