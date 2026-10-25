"""Single entry point of the AI layer, called by the backend (/api/chat).

    from ai_agents.main_agent import run_copilot_agent
    result = run_copilot_agent("Total sales by region?")

Returned dict:
    answer : str
    sources: [{"file": str, "page": int, "snippet": str}]
    chart  : {"type", "x", "y", "figure": <plotly figure as dict>} or None
    sql    : executed SQL query or None
    route  : router decision (sql | rag | both | chart | general)
    error  : error message or None

Quick test:
    python -m ai_agents.main_agent "total sales by region"
"""
from functools import lru_cache

from ai_agents.workflow import build_graph


@lru_cache(maxsize=1)
def _graph():
    return build_graph()


def run_copilot_agent(question: str, history: list | None = None) -> dict:
    """history is accepted for the future (multi-turn chat) but not used yet."""
    try:
        state = _graph().invoke({"question": question, "errors": []})
    except Exception as exc:
        return {
            "answer": "Sorry, I could not process this question.",
            "sources": [],
            "chart": None,
            "sql": None,
            "route": None,
            "error": str(exc)[:300],
        }

    sources = [
        {"file": c["file"], "page": c["page"], "snippet": c["snippet"][:300]}
        for c in state.get("rag_chunks", [])
    ]
    errors = state.get("errors", [])
    return {
        "answer": state.get("answer", ""),
        "sources": sources,
        "chart": state.get("chart"),
        "sql": (state.get("sql_result") or {}).get("sql") or None,
        "route": state.get("route"),
        "error": "; ".join(errors) if errors else None,
    }


if __name__ == "__main__":
    import json
    import sys

    q = " ".join(sys.argv[1:]) or "What are the total sales by region?"
    out = run_copilot_agent(q)
    if out["chart"]:
        out["chart"]["figure"] = "<plotly figure omitted>"  # keep the console readable
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
