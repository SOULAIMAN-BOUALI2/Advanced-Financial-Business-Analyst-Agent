"""Secure Text-to-SQL tool.

Pipeline: schema -> LLM writes SQL -> validate (SELECT only) -> run in a
READ ONLY transaction with a timeout and a row limit.

Public API used by workflow.py:
    run_text_to_sql(question) -> {"sql", "columns", "rows", "error"}

Quick test:
    python -m ai_agents.sql_tool "total sales by region"
"""
import os
import re
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from ai_agents.llm import TRANSIENT_MARKERS, ask
from ai_agents.prompts import TEXT_TO_SQL_PROMPT

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
MAX_ROWS = int(os.getenv("SQL_MAX_ROWS", "200"))
TIMEOUT_MS = int(os.getenv("SQL_TIMEOUT_MS", "10000"))
MAX_ATTEMPTS = 2  # first try + one self-correction

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|do|"
    r"execute|merge|vacuum|analyze|set|reset|listen|notify|lock|dblink|lo_import|lo_export)\b",
    re.IGNORECASE,
)
SYSTEM_TABLES = re.compile(r"\b(langchain_pg_\w+|pg_\w+|information_schema)\b", re.IGNORECASE)
# The LLM may only read these relations (comma separated in .env). The flat view
# built by the data engineer already contains the joins, so no JOIN is needed.
ALLOWED_RELATIONS = {
    r.strip().lower()
    for r in os.getenv("SQL_ALLOWED_TABLES", "v_sales_enriched").split(",")
    if r.strip()
}


# ----------------------------------------------------------------- database
@lru_cache(maxsize=1)
def get_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (check your .env file).")
    return create_engine(url.replace("postgresql+psycopg2://", "postgresql+psycopg://"))


@lru_cache(maxsize=1)
def get_schema_description() -> str:
    """Describe the allowed relations, with the possible values of small text columns."""
    query = text(
        """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ANY(:allowed)
        ORDER BY table_name, ordinal_position
        """
    )
    tables: dict[str, list[tuple[str, str]]] = {}
    lines = []
    with get_engine().connect() as conn:
        for table, column, dtype in conn.execute(query, {"allowed": sorted(ALLOWED_RELATIONS)}):
            tables.setdefault(table, []).append((column, dtype))
        for table, cols in tables.items():
            parts = []
            for column, dtype in cols:
                desc = f"{column} {dtype}"
                if dtype in ("text", "character varying"):
                    values = [
                        row[0]
                        for row in conn.execute(
                            text(f'SELECT DISTINCT "{column}" FROM "{table}" '
                                 f'WHERE "{column}" IS NOT NULL LIMIT 11')
                        )
                    ]
                    if 0 < len(values) <= 10:
                        desc += " (values: " + ", ".join(sorted(map(str, values))) + ")"
                parts.append(desc)
            lines.append(f"{table}({', '.join(parts)})")
    return "\n".join(lines) if lines else "(no tables found)"


# --------------------------------------------------------------- validation
def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


def validate_sql(sql: str) -> str:
    """Return a safe, limited SELECT query or raise ValueError."""
    cleaned = _strip_comments(sql).strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("Empty query.")
    if ";" in cleaned:
        raise ValueError("Only one statement is allowed.")
    if not re.match(r"^(select|with)\b", cleaned, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed.")
    if FORBIDDEN.search(cleaned):
        raise ValueError("The query contains a forbidden keyword.")
    if SYSTEM_TABLES.search(cleaned):
        raise ValueError("Access to system tables is not allowed.")
    cte_names = {m.lower() for m in re.findall(r"\b(\w+)\s+as\s*\(", cleaned, re.IGNORECASE)}
    scan = re.sub(r"extract\s*\(\s*\w+\s+from\s+[^)]*\)", " ", cleaned, flags=re.IGNORECASE)
    for relation in re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)", scan, re.IGNORECASE):
        name = relation.lower().split(".")[-1]
        if name not in ALLOWED_RELATIONS and name not in cte_names:
            raise ValueError(f"Table not allowed: {relation}")
    if not re.search(r"\blimit\s+\d+", cleaned, re.IGNORECASE):
        cleaned = f"SELECT * FROM ({cleaned}) AS q LIMIT {MAX_ROWS}"
    return cleaned


def _jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def execute_readonly(sql: str) -> tuple[list[str], list[list]]:
    with get_engine().connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text(f"SET LOCAL statement_timeout = {TIMEOUT_MS}"))
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [[_jsonable(v) for v in row] for row in result.fetchmany(MAX_ROWS)]
        conn.rollback()
    return columns, rows


# ---------------------------------------------------------------------- LLM
def _as_text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)


def _clean_llm_sql(raw: str) -> str:
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE)
    return raw.replace("```", "").strip()


def generate_sql(question: str, schema: str, previous_sql: str = "", error: str = "") -> str:
    prompt = TEXT_TO_SQL_PROMPT.format(schema=schema, question=question)
    if error:
        prompt += f"\n\nYour previous query failed.\nQuery: {previous_sql}\nError: {error}\nFix it and output only the corrected SQL."
    return _clean_llm_sql(ask(prompt))


# --------------------------------------------------------------- public API
def run_text_to_sql(question: str) -> dict:
    schema = get_schema_description()
    sql, error = "", ""
    for _ in range(MAX_ATTEMPTS):
        try:
            sql = generate_sql(question, schema, previous_sql=sql, error=error)
            safe_sql = validate_sql(sql)
            columns, rows = execute_readonly(safe_sql)
            return {"sql": safe_sql, "columns": columns, "rows": rows, "error": None}
        except Exception as exc:  # validation or SQL error -> let the LLM retry once
            error = str(exc).splitlines()[0][:300]
            if any(marker in str(exc) for marker in TRANSIENT_MARKERS):
                break  # quota / overload: asking the model again would only waste quota
    return {"sql": sql, "columns": [], "rows": [], "error": error}


if __name__ == "__main__":
    import json
    import sys

    q = " ".join(sys.argv[1:]) or "total sales by region"
    print("SCHEMA:\n" + get_schema_description() + "\n")
    print(json.dumps(run_text_to_sql(q), indent=2, ensure_ascii=False, default=str))
