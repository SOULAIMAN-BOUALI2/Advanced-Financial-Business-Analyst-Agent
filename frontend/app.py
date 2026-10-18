import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# Configuration de la page
st.set_page_config(
    page_title="GenInvest Copilot - Chat Interface", 
    page_icon="🤖", 
    layout="centered", # Mode centré comme ChatGPT pour un look plus épuré
    initial_sidebar_state="collapsed"
)

# Style CSS pour masquer les éléments Streamlit et styliser le chat
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Style de la boîte de message */
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

API_URL = "http://127.0.0.1:8000"

# En-tête minimaliste et professionnel
st.title("🤖 GenInvest Copilot")
st.markdown("Votre assistant intelligent pour l'analyse financière et la génération de graphiques dynamiques.")
st.markdown("---")

# Initialisation de l'historique des messages
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Bonjour ! Je suis votre copilote financier. Posez-moi une question sur vos rapports ou demandez-moi de tracer un graphique (ex: *'Montre-moi l'évolution des ventes en graphique'*).", "chart": None}
    ]

# Affichage de tout l'historique de la conversation
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
        st.markdown(message["content"])
        
        # Si un graphique est attaché au message, on l'affiche directement dans la bulle
        if message.get("chart") is not None:
            st.plotly_chart(message["chart"], use_container_width=True)

# Zone de saisie du chat (en bas de la page comme ChatGPT)
if prompt := st.chat_input("Écrivez votre message ou demandez un graphique..."):
    
    # 1. Ajouter et afficher le message utilisateur
    st.session_state.messages.append({"role": "user", "content": prompt, "chart": None})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # 2. Simulation de la réponse de l'IA (Ici on simulera l'agent du Membre 2)
    # Détection si l'utilisateur demande un graphique ou du texte simple
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Analyse en cours..."):
            
            # Appel API Backend (simulé ou réel)
            try:
                res = requests.post(f"{API_URL}/api/chat", json={"query": prompt}, timeout=3)
                data = res.json() if res.status_code == 200 else {}
                bot_text = data.get("answer", f"Analyse traitée pour : '{prompt}'")
                sources = data.get("sources", ["Rapport_Financier_2025.pdf"])
            except:
                bot_text = f"Analyse générée avec succès pour votre requête : *'{prompt}'*."
                sources = ["Rapport_Trimestriel_Q4.pdf"]

            # Formatage de la réponse texte + sources
            full_reply = f"{bot_text}\n\n*📌 Sources : {', '.join(sources)}*"
            st.markdown(full_reply)

            # Condition magique : Si l'utilisateur demande un graphique, on le génère et l'imbrique dans le chat !
            fig_to_display = None
            if any(keyword in prompt.lower() for keyword in ["graphique", "trace", "tendance", "ventes", "visualise", "courbe"]):
                # Exemple de génération d'un graphique Plotly dynamique à la volée
                df_sample = pd.DataFrame({
                    "Mois": ["Janvier", "Février", "Mars", "Avril"],
                    "Ventes": [10000, 15000, 12000, 18000]
                })
                fig_to_display = px.bar(
                    df_sample, x="Mois", y="Ventes", 
                    title="Graphique généré par le Copilote",
                    color_discrete_sequence=["#2563EB"]
                )
                fig_to_display.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", 
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=30, b=10, l=10, r=10)
                )
                st.plotly_chart(fig_to_display, use_container_width=True)

    # Enregistrement dans l'historique de session
    st.session_state.messages.append({
        "role": "assistant", 
        "content": full_reply, 
        "chart": fig_to_display
    })