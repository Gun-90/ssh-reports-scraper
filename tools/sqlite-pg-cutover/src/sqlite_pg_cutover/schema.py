from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable


SQLITE_INTERNAL_PREFIX = "sqlite_"


@dataclass(frozen=True)
class Column:
    name: str
    pg_name: str
    sqlite_type: str
    pg_type: str
    not_null: bool
    primary_key_pos: int
    default: str | None


@dataclass(frozen=True)
class Table:
    name: str
    pg_name: str
    columns: tuple[Column, ...]
    row_count: int

    @property
    def primary_key_columns(self) -> tuple[Column, ...]:
        return tuple(sorted((c for c in self.columns if c.primary_key_pos), key=lambda c: c.primary_key_pos))


def normalize_identifier(name: str) -> str:
    """Convert loose SQLite identifiers into plain PostgreSQL-safe lowercase identifiers."""
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", name.strip()).strip("_").lower()
    if not cleaned:
        cleaned = "unnamed"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sqlite_type_to_postgres(sqlite_type: str) -> str:
    t = (sqlite_type or "").strip().upper()
    if not t:
        return "text"
    if "INT" in t:
        return "bigint"
    if any(x in t for x in ("CHAR", "CLOB", "TEXT", "VARCHAR", "NCHAR", "NVARCHAR")):
        return "text"
    if "BLOB" in t:
        return "bytea"
    if any(x in t for x in ("REAL", "FLOA", "DOUB")):
        return "double precision"
    if any(x in t for x in ("NUM", "DEC", "BOOL")):
        return "numeric"
    if "DATE" in t or "TIME" in t:
        return "text"
    return "text"


def connect_sqlite(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def list_sqlite_tables(conn: sqlite3.Connection, include: Iterable[str] | None = None) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    include_set = set(include or [])
    tables = []
    for row in rows:
        name = row["name"]
        if name.startswith(SQLITE_INTERNAL_PREFIX):
            continue
        if include_set and name not in include_set:
            continue
        tables.append(name)
    return tables


def inspect_tables(conn: sqlite3.Connection, include: Iterable[str] | None = None) -> list[Table]:
    tables = []
    for table_name in list_sqlite_tables(conn, include):
        columns = []
        for col in conn.execute(f"PRAGMA table_info({quote_ident(table_name)})").fetchall():
            sqlite_type = col["type"] or ""
            columns.append(
                Column(
                    name=col["name"],
                    pg_name=normalize_identifier(col["name"]),
                    sqlite_type=sqlite_type,
                    pg_type=sqlite_type_to_postgres(sqlite_type),
                    not_null=bool(col["notnull"]),
                    primary_key_pos=int(col["pk"] or 0),
                    default=col["dflt_value"],
                )
            )
        count = conn.execute(f"SELECT COUNT(*) AS count FROM {quote_ident(table_name)}").fetchone()["count"]
        tables.append(
            Table(
                name=table_name,
                pg_name=normalize_identifier(table_name),
                columns=tuple(columns),
                row_count=int(count),
            )
        )
    return tables


def render_create_table(table: Table) -> str:
    lines = []
    for col in table.columns:
        line = f"    {quote_ident(col.pg_name)} {col.pg_type}"
        if col.not_null or col.primary_key_pos:
            line += " NOT NULL"
        lines.append(line)

    pk_cols = table.primary_key_columns
    if pk_cols:
        pk = ", ".join(quote_ident(c.pg_name) for c in pk_cols)
        lines.append(f"    PRIMARY KEY ({pk})")

    body = ",\n".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {quote_ident(table.pg_name)} (\n{body}\n);"


def render_schema(tables: Iterable[Table]) -> str:
    return "\n\n".join(render_create_table(table) for table in tables) + "\n"
