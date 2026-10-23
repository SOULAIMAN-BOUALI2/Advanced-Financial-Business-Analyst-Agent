"""LangGraph multi-agent workflow.

    question -> router --+--> sql ------+--> (rag if route == both) --> synthesis
                         +--> rag ------+
                         +--> chart ----+
                         +--> general --+

Note: node names are prefixed with "n_" because LangGraph forbids a node name
that is also a state key (e.g. "chart").
"""
import json
import re
from typing import Optional, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from ai_agents.llm import ask
from ai_agents.prompts import GENERAL_PROMPT, ROUTER_PROMPT, SYNTHESIS_PROMPT
from ai_agents.rag_engine import search
from ai_agents.sql_tool import run_text_to_sql

VALID_ROUTES = {"sql", "rag", "both", "chart", "general"}
MAX_ROWS_IN_PROMPT = 50


class AgentState(TypedDict, total=False):
    question: str
    route: str
    sql_result: Optional[dict]
    rag_chunks: list
    chart: Optional[dict]
    answer: str
    errors: list


# --------------------------------------------------------------------- router
def router_node(state: AgentState) -> dict:
    raw = ask(ROUTER_PROMPT.format(question=state["question"]), fast=True)
    words = re.findall(r"[a-z]+", raw.lower())
    route = words[0] if words and words[0] in VALID_ROUTES else "both"  # safe default
    return {"route": route}


# ------------------------------------------------------------------ SQL / RAG
def sql_node(state: AgentState) -> dict:
    return {"sql_result": run_text_to_sql(state["question"])}


def rag_node(state: AgentState) -> dict:
    try:
        return {"rag_chunks": search(state["question"], k=4)}
    except Exception as exc:
        return {"rag_chunks": [], "errors": state.get("errors", []) + [f"RAG: {exc}"]}


# ------------------------------------------------------------ chart gateway
def _load_analytics():
    """Use Member 1's analytics.py if present, otherwise the dev stub."""
    try:
        from data_engineering import analytics  # type: ignore
        return analytics
    except ImportError:
        from ai_agents import dev_analytics_stub as analytics
        return analytics


def _chart_prompt(question: str, columns: list, rows: list) -> str:
    sample = "\n".join(" | ".join(map(str, r)) for r in rows[:5])
    return (
        "You choose how to plot a SQL result. Answer with ONLY a JSON object like "
        '{"chart": "bar", "x": "column_name", "y": "column_name"}.\n'
        "chart must be one of: line (trend over time), bar (comparison between "
        "categories), pie (share of a total). x is the label/category/date column, "
        "y is the numeric column. Use the exact column names.\n\n"
        f"User request: {question}\n"
        f"Columns: {', '.join(columns)}\n"
        f"First rows:\n{sample}\n\nJSON:"
    )


def chart_node(state: AgentState) -> dict:
    """The LLM picks a chart function and its columns; it never writes plotting code."""
    result = run_text_to_sql(state["question"])
    update: dict = {"sql_result": result, "chart": None}
    if result["error"] or not result["rows"]:
        return update
    try:
        raw = ask(_chart_prompt(state["question"], result["columns"], result["rows"]), fast=True)
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        spec = json.loads(match.group(0))
        chart_type, x, y = spec["chart"], spec["x"], spec["y"]

        df = pd.DataFrame(result["rows"], columns=result["columns"])
        if chart_type not in {"line", "bar", "pie"} or x not in df.columns or y not in df.columns:
            raise ValueError(f"invalid chart spec: {spec}")
        if not pd.api.types.is_numeric_dtype(df[y]):
            raise ValueError(f"column {y} is not numeric")

        analytics = _load_analytics()
        if chart_type == "line":
            fig = analytics.plot_line_chart(df, x, y)
        elif chart_type == "bar":
            fig = analytics.plot_bar_chart(df, x, y)
        else:
            fig = analytics.plot_pie_chart(df, x, y)
        update["chart"] = {"type": chart_type, "x": x, "y": y, "figure": json.loads(fig.to_json())}
    except Exception as exc:
        update["errors"] = state.get("errors", []) + [f"Chart: {exc}"]
    return update


# ------------------------------------------------------------------ synthesis
def _format_sql(result: Optional[dict]) -> str:
    if not result:
        return "(none)"
    if result.get("error"):
        return f"(the query failed: {result['error']})"
    lines = [" | ".join(result["columns"])]
    lines += [" | ".join(str(v) for v in row) for row in result["rows"][:MAX_ROWS_IN_PROMPT]]
    if len(result["rows"]) > MAX_ROWS_IN_PROMPT:
        lines.append(f"... ({len(result['rows'])} rows in total)")
    return "\n".join(lines)


def _format_docs(chunks: list) -> str:
    if not chunks:
        return "(none)"
    return "\n\n".join(f"[{c['file']}, p.{c['page']}] {c['snippet']}" for c in chunks)


def synthesis_node(state: AgentState) -> dict:
    if state.get("route") == "general":
        return {"answer": ask(GENERAL_PROMPT.format(question=state["question"]))}
    result = state.get("sql_result")
    chart = state.get("chart")
    prompt = SYNTHESIS_PROMPT.format(
        question=state["question"],
        sql=(result or {}).get("sql") or "(none)",
        sql_result=_format_sql(result),
        documents=_format_docs(state.get("rag_chunks", [])),
        chart_info=f"a {chart['type']} chart was generated and is displayed with the answer"
        if chart else "none",
    )
    return {"answer": ask(prompt)}


# ---------------------------------------------------------------------- graph
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("n_router", router_node)
    g.add_node("n_sql", sql_node)
    g.add_node("n_rag", rag_node)
    g.add_node("n_chart", chart_node)
    g.add_node("n_synthesis", synthesis_node)

    g.add_edge(START, "n_router")
    g.add_conditional_edges(
        "n_router",
        lambda s: s["route"],
        {"sql": "n_sql", "both": "n_sql", "rag": "n_rag", "chart": "n_chart", "general": "n_synthesis"},
    )
    g.add_conditional_edges(
        "n_sql",
        lambda s: "n_rag" if s["route"] == "both" else "n_synthesis",
        {"n_rag": "n_rag", "n_synthesis": "n_synthesis"},
    )
    g.add_edge("n_rag", "n_synthesis")
    g.add_edge("n_chart", "n_synthesis")
    g.add_edge("n_synthesis", END)
    return g.compile()
