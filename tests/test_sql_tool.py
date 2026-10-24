"""Unit tests for the Text-to-SQL safety layer. They need neither the database nor the LLM.

Run from the project root:  python -m pytest tests/test_sql_tool.py -v
"""
import pytest

from ai_agents.sql_tool import validate_sql


def test_accepts_select_on_the_view_and_adds_a_limit():
    sql = validate_sql("SELECT region, SUM(sales_amount) AS total FROM v_sales_enriched GROUP BY region")
    assert "LIMIT" in sql.upper()


def test_keeps_an_existing_limit():
    sql = validate_sql("SELECT region FROM v_sales_enriched LIMIT 5")
    assert sql.upper().count("LIMIT") == 1


def test_accepts_extract_from_date():
    validate_sql(
        "SELECT EXTRACT(YEAR FROM date) AS y, SUM(sales_amount) AS total "
        "FROM v_sales_enriched GROUP BY y ORDER BY y"
    )


def test_accepts_a_cte():
    validate_sql(
        "WITH t AS (SELECT region, SUM(sales_amount) AS s FROM v_sales_enriched GROUP BY region) "
        "SELECT * FROM t"
    )


@pytest.mark.parametrize(
    "bad_sql",
    [
        "DELETE FROM v_sales_enriched",
        "DROP TABLE sales",
        "UPDATE sales SET profit = 0",
        "INSERT INTO sales (region) VALUES ('x')",
        "SELECT 1; DROP TABLE sales",
        "SELECT * FROM sales",
        "SELECT * FROM clients",
        "SELECT * FROM v_sales_enriched JOIN clients ON true",
        "SELECT * FROM langchain_pg_embedding",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM information_schema.tables",
        "",
    ],
)
def test_rejects_unsafe_or_out_of_scope_queries(bad_sql):
    with pytest.raises(ValueError):
        validate_sql(bad_sql)
