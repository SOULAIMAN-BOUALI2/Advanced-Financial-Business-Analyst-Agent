from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="GenInvest Copilot API", version="1.0")

class ChatRequest(BaseModel):
    query: str

@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API de GenInvest Copilot !"}

@app.get("/api/dashboard")
def get_dashboard_data():
    """
    Route pour récupérer les données agrégées et KPIs 
    (préparées par le Membre 1).
    """
    return {
        "total_sales": "1,250,000 MAD",
        "net_margin": "+14.2%",
        "top_region": "Casablanca"
    }

@app.post("/api/chat")
def chat_with_copilot(request: ChatRequest):
    """
    Route du chat : Reçoit la question de l'utilisateur et appellera 
    la fonction d'entrée de l'agent du Membre 2 (run_copilot_agent).
    """
    user_message = request.query
    
    # ⚠️ TODO (Intégration future) : Appeler ici la fonction du Membre 2
    # response = run_copilot_agent(user_message)
    
    # Réponse simulée pour tester l'API :
    return {
        "answer": f"Analyse réalisée pour votre requête : '{user_message}'. (Connexion à l'agent LangGraph en cours)",
        "sources": ["Rapport_Financier_2025.pdf (page 4)"]
    }