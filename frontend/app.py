import os

import plotly.io as pio
import requests
import streamlit as st

st.set_page_config(
    page_title="GenInvest Copilot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("API_URL", "http://backend:8000").rstrip("/")

st.markdown(
    """
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .stChatMessage {padding: 1rem; border-radius: 0.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def api_get(path: str) -> dict:
    response = requests.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict) -> dict:
    response = requests.post(f"{API_URL}{path}", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def format_source(source: dict) -> str:
    file_name = source.get("file", "document inconnu")
    page = source.get("page")
    return f"{file_name} (page {page})" if page else file_name


def render_chart(chart: dict) -> None:
    figure = chart.get("figure") if chart else None
    if not figure:
        return
    st.plotly_chart(pio.from_json(figure) if isinstance(figure, str) else figure, use_container_width=True)


st.title("🤖 GenInvest Copilot")
st.caption("Analyse financière fondée sur les données PostgreSQL et les rapports PDF.")

with st.sidebar:
    st.header("Tableau de bord")
    try:
        kpis = api_get("/api/dashboard")
        st.metric("Chiffre d'affaires", f"{kpis['total_sales']:,.2f}")
        st.metric("Marge nette", kpis["net_margin"])
        st.metric("Meilleure région", kpis["top_region"] or "N/A")
        st.metric("Commandes", f"{kpis['total_orders']:,}")
    except requests.RequestException as exc:
        st.error(f"Dashboard indisponible : {exc}")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Bonjour ! Posez une question sur les ventes ou les rapports PDF. "
                "Je peux aussi générer un graphique à partir des données réelles."
            ),
            "chart": None,
            "sources": [],
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
        st.markdown(message["content"])
        render_chart(message.get("chart"))
        sources = message.get("sources", [])
        if sources:
            st.caption("📌 Sources : " + ", ".join(format_source(source) for source in sources))

if prompt := st.chat_input("Posez votre question..."):
    st.session_state.messages.append({"role": "user", "content": prompt, "chart": None, "sources": []})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Analyse en cours..."):
            try:
                data = api_post("/api/chat", {"query": prompt})
                answer = data.get("answer") or "L'agent n'a pas retourné de réponse."
                chart = data.get("chart")
                sources = data.get("sources", [])
                error = data.get("error")
                st.markdown(answer)
                if error:
                    st.warning(f"Traitement partiel : {error}")
                render_chart(chart)
                if sources:
                    st.caption("📌 Sources : " + ", ".join(format_source(source) for source in sources))
            except requests.RequestException as exc:
                answer = f"Impossible de contacter le backend : {exc}"
                chart, sources = None, []
                st.error(answer)
            except (KeyError, ValueError, TypeError) as exc:
                answer = f"Réponse invalide du backend : {exc}"
                chart, sources = None, []
                st.error(answer)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "chart": chart, "sources": sources}
    )
