from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ai_agents.main_agent import run_copilot_agent
from data_engineering.analytics import get_kpi_summary

app = FastAPI(title="GenInvest Copilot API", version="1.0")


class ChatRequest(BaseModel):
    query: str


@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API de GenInvest Copilot !"}


@app.get("/api/dashboard")
def get_dashboard_data():
    """Return dashboard KPIs computed from the sales database."""
    try:
        kpis = get_kpi_summary()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Dashboard unavailable: {exc}") from exc

    return {
        **kpis,
        "net_margin": f"{kpis['profit_margin_pct']:.2f}%",
        "top_region": kpis["best_region"],
    }


@app.post("/api/chat")
def chat_with_copilot(request: ChatRequest):
    """Run the agent and return its answer, sources and optional chart."""
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be empty")
    return run_copilot_agent(query)
