from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .compare import compare_table
from .copy import copy_tables
from .postgres import connect_postgres
from .schema import connect_sqlite, inspect_tables, render_schema


def _table_filter(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _postgres_dsn(value: str | None) -> str:
    dsn = value or os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("PostgreSQL DSN required. Pass --postgres or set POSTGRES_DSN.")
    return dsn


def _load_tables(sqlite_path: str, tables: str | None):
    sqlite_conn = connect_sqlite(sqlite_path)
    return sqlite_conn, inspect_tables(sqlite_conn, _table_filter(tables))


def cmd_plan(args) -> int:
    sqlite_conn, tables = _load_tables(args.sqlite, args.tables)
    try:
        print("# SQLite -> PostgreSQL Cutover Plan")
        print()
        print(f"SQLite: {args.sqlite}")
        print(f"Tables: {len(tables)}")
        print()
        for table in tables:
            pk = ", ".join(c.name for c in table.primary_key_columns) or "-"
            print(f"- {table.name} -> {table.pg_name}: rows={table.row_count}, columns={len(table.columns)}, pk={pk}")
        print()
        print("Checklist:")
        print("1. Stop or freeze application writes.")
        print("2. Back up the SQLite file.")
        print("3. Generate and review PostgreSQL DDL.")
        print("4. Apply DDL to PostgreSQL.")
        print("5. Copy rows in batches.")
        print("6. Compare counts and samples.")
        print("7. Switch application DATABASE_URL/POSTGRES_DSN.")
        print("8. Keep SQLite as an archive unless dual-write is still active.")
        return 0
    finally:
        sqlite_conn.close()


def cmd_ddl(args) -> int:
    sqlite_conn, tables = _load_tables(args.sqlite, args.tables)
    try:
        ddl = render_schema(tables)
        if args.output:
            Path(args.output).write_text(ddl, encoding="utf-8")
            print(f"Wrote PostgreSQL DDL: {args.output}")
        else:
            print(ddl)
        return 0
    finally:
        sqlite_conn.close()


def cmd_copy(args) -> int:
    sqlite_conn, tables = _load_tables(args.sqlite, args.tables)
    pg_conn = connect_postgres(_postgres_dsn(args.postgres))
    try:
        result = copy_tables(
            sqlite_conn,
            pg_conn,
            tables,
            batch_size=args.batch_size,
            overwrite=args.overwrite,
        )
        for table_name, (attempted, total) in result.items():
            print(f"{table_name}: copied_or_attempted={attempted}, sqlite_total={total}")
        return 0
    finally:
        pg_conn.close()
        sqlite_conn.close()


def cmd_compare(args) -> int:
    sqlite_conn, tables = _load_tables(args.sqlite, args.tables)
    pg_conn = connect_postgres(_postgres_dsn(args.postgres))
    failed = False
    try:
        for table in tables:
            result = compare_table(sqlite_conn, pg_conn, table, sample_size=args.sample_size)
            pg_count = "ERROR" if result.postgres_count is None else str(result.postgres_count)
            sample = "n/a" if result.sample_matches is None else ("ok" if result.sample_matches else "fail")
            status = "ok" if result.count_matches and result.sample_matches is not False else "fail"
            print(
                f"{status} {table.name}: sqlite={result.sqlite_count}, postgres={pg_count}, sample={sample}"
                + (f" ({result.note})" if result.note else "")
            )
            if status != "ok":
                failed = True
        return 1 if failed else 0
    finally:
        pg_conn.close()
        sqlite_conn.close()


def cmd_all(args) -> int:
    sqlite_conn, tables = _load_tables(args.sqlite, args.tables)
    pg_conn = connect_postgres(_postgres_dsn(args.postgres))
    try:
        if args.apply_ddl:
            ddl = render_schema(tables)
            with pg_conn.cursor() as cur:
                cur.execute(ddl)
            pg_conn.commit()
            print("Applied generated DDL.")
        result = copy_tables(
            sqlite_conn,
            pg_conn,
            tables,
            batch_size=args.batch_size,
            overwrite=args.overwrite,
        )
        for table_name, (attempted, total) in result.items():
            print(f"{table_name}: copied_or_attempted={attempted}, sqlite_total={total}")

        failed = False
        for table in tables:
            compare = compare_table(sqlite_conn, pg_conn, table, sample_size=args.sample_size)
            status = "ok" if compare.count_matches and compare.sample_matches is not False else "fail"
            print(f"{status} compare {table.name}: sqlite={compare.sqlite_count}, postgres={compare.postgres_count}")
            if status != "ok":
                failed = True
        return 1 if failed else 0
    finally:
        pg_conn.close()
        sqlite_conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sqlite-pg-cutover",
        description="Pragmatic SQLite to PostgreSQL cutover helper.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p, postgres=False):
        p.add_argument("--sqlite", required=True, help="Path to SQLite database file.")
        p.add_argument("--tables", help="Comma-separated table allowlist.")
        if postgres:
            p.add_argument("--postgres", help="PostgreSQL DSN. Defaults to POSTGRES_DSN or DATABASE_URL.")

    p = sub.add_parser("plan", help="Inspect SQLite and print a cutover checklist.")
    add_common(p)
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("ddl", help="Generate PostgreSQL CREATE TABLE statements.")
    add_common(p)
    p.add_argument("--output", "-o", help="Write DDL to a file instead of stdout.")
    p.set_defaults(func=cmd_ddl)

    p = sub.add_parser("copy", help="Copy SQLite rows into PostgreSQL.")
    add_common(p, postgres=True)
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--overwrite", action="store_true", help="Update existing rows when a primary key conflict occurs.")
    p.set_defaults(func=cmd_copy)

    p = sub.add_parser("compare", help="Compare row counts and primary-key samples.")
    add_common(p, postgres=True)
    p.add_argument("--sample-size", type=int, default=20)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("all", help="Optionally apply DDL, copy rows, then compare.")
    add_common(p, postgres=True)
    p.add_argument("--apply-ddl", action="store_true")
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--sample-size", type=int, default=20)
    p.set_defaults(func=cmd_all)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
