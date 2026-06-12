# sqlite-pg-cutover

`sqlite-pg-cutover` is a small, pragmatic SQLite to PostgreSQL cutover toolkit.

It is built for the common path where an app starts with SQLite, grows real data,
and then needs a PostgreSQL migration that is boring, inspectable, and repeatable.

## What It Does

- Inspect SQLite schema and row counts
- Generate PostgreSQL DDL with lowercase identifier normalization
- Copy table data in batches
- Use `ON CONFLICT DO NOTHING` for idempotent re-runs when a primary key exists
- Compare row counts and sampled rows between SQLite and PostgreSQL
- Print a cutover checklist for production use

## Install

From this folder:

```bash
uv tool install .
```

Or during development:

```bash
uv run sqlite-pg-cutover --help
```

After publishing:

```bash
uvx sqlite-pg-cutover --help
pipx run sqlite-pg-cutover --help
```

## Quick Start

```bash
export POSTGRES_DSN='postgresql://user:password@localhost:5432/mydb'

sqlite-pg-cutover plan --sqlite ./app.db
sqlite-pg-cutover ddl --sqlite ./app.db --output schema.pg.sql
psql "$POSTGRES_DSN" -f schema.pg.sql
sqlite-pg-cutover copy --sqlite ./app.db --postgres "$POSTGRES_DSN"
sqlite-pg-cutover compare --sqlite ./app.db --postgres "$POSTGRES_DSN"
```

One-shot mode:

```bash
sqlite-pg-cutover all \
  --sqlite ./app.db \
  --postgres "$POSTGRES_DSN" \
  --apply-ddl
```

## Defaults

- SQLite table and column names are normalized to lowercase by default.
- SQLite internal tables are skipped.
- Data copy is batch-based.
- Existing PostgreSQL rows are not overwritten by default.

## Why Not A Giant Migration Framework?

This tool is intentionally narrow. It is for the 80% case:

- small production apps
- LLM-generated prototypes that accidentally became real
- SQLite tables that now need PostgreSQL durability, backups, and remote access
- teams that need a dry-run plan and compare report before cutover

For complex schema migrations, use Alembic, Sqitch, or a dedicated ETL pipeline.

## Cutover Checklist

```bash
sqlite-pg-cutover plan --sqlite ./app.db
```

The checklist reminds you to:

- take a SQLite file backup
- run DDL in PostgreSQL
- copy rows
- compare row counts
- compare samples
- freeze writes before final copy
- switch application config
- keep SQLite as an archive, not a live rollback, unless dual-write remains active
