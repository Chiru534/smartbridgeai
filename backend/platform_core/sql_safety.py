from __future__ import annotations

import re
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .config import settings

READ_ONLY_PREFIX = re.compile(r"^\s*(SELECT|WITH|SHOW|EXPLAIN|PRAGMA)\b", re.IGNORECASE)
BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|ATTACH|DETACH|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)


def normalize_sql(sql: str) -> str:
    return (sql or "").strip()


def has_multiple_statements(sql: str) -> bool:
    trimmed = normalize_sql(sql)
    if not trimmed:
        return False
    if trimmed.endswith(";"):
        trimmed = trimmed[:-1].rstrip()
    return ";" in trimmed


def ensure_read_only_sql(sql: str) -> str:
    cleaned = normalize_sql(sql)
    if not cleaned:
        raise ValueError("SQL is required")
    if has_multiple_statements(cleaned):
        raise ValueError("Only a single SQL statement is allowed")
    if BLOCKED_KEYWORDS.search(cleaned):
        raise ValueError("Only read-only SQL statements are allowed")
    if not READ_ONLY_PREFIX.match(cleaned):
        raise ValueError("The SQL agent only allows SELECT/WITH/SHOW/EXPLAIN/PRAGMA statements")
    return cleaned.rstrip(";")


def enforce_limit(sql: str, row_limit: int | None = None) -> str:
    row_limit = row_limit or settings.sql_agent_row_limit
    cleaned = ensure_read_only_sql(sql)
    if re.search(r"\blimit\s+\d+\b", cleaned, re.IGNORECASE):
        return cleaned
    if cleaned.lower().startswith(("show", "pragma", "explain")):
        return cleaned
    return f"{cleaned} LIMIT {row_limit}"


def list_database_tables(engine: Engine) -> list[dict[str, Any]]:
    inspector = inspect(engine)
    tables = []
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        tables.append(
            {
                "table_name": table_name,
                "column_count": len(columns),
                "columns": [column["name"] for column in columns],
            }
        )
    return sorted(tables, key=lambda item: item["table_name"])


def describe_table(engine: Engine, table_name: str) -> dict[str, Any]:
    cleaned_name = normalize_sql(table_name)
    if not cleaned_name:
        raise ValueError("table_name is required")
    inspector = inspect(engine)
    available = inspector.get_table_names()
    if cleaned_name not in available:
        raise ValueError(f"Table '{cleaned_name}' was not found")
    columns = inspector.get_columns(cleaned_name)
    return {
        "table_name": cleaned_name,
        "columns": [
            {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": bool(column.get("nullable", True)),
                "default": str(column.get("default")) if column.get("default") is not None else None,
            }
            for column in columns
        ],
    }


def _build_explain_sql(engine: Engine, sql: str) -> str:
    if sql.lower().startswith("explain"):
        return sql
    if engine.dialect.name == "sqlite":
        return f"EXPLAIN QUERY PLAN {sql}"
    return f"EXPLAIN {sql}"


def run_safe_sql(engine: Engine, sql: str, row_limit: int | None = None) -> dict[str, Any]:
    executable_sql = enforce_limit(sql, row_limit=row_limit)
    explain_sql = _build_explain_sql(engine, executable_sql)

    with engine.begin() as connection:
        if engine.dialect.name.startswith("postgres"):
            connection.exec_driver_sql(f"SET LOCAL statement_timeout = '{settings.sql_agent_timeout_ms}ms'")
            connection.exec_driver_sql("SET LOCAL default_transaction_read_only = on")

        explain_rows = connection.execute(text(explain_sql)).fetchall()
        result = connection.execute(text(executable_sql))
        rows = result.mappings().all()

    return {
        "sql": executable_sql,
        "row_count": len(rows),
        "rows": [dict(row) for row in rows],
        "plan": [tuple(row) for row in explain_rows],
    }
