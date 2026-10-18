# 📊 GenInvest Copilot : Plateforme d'Analyse Financière & Business Intelligence (PFE ENSIAS)

Plateforme intelligente d'aide à la décision financière combinant l'analyse de données structurées et non structurées, propulsée par une architecture d'agents autonomes et un LLM.

---

## 🏗️ Architecture du Projet
Le projet est conçu pour couvrir l'ensemble des métiers de la data et du génie logiciel :
* **Data Engineering & Analytics (Membre 1) :** Ingestion des fichiers tabulaires (CSV/Excel) et structuration dans une base de données **PostgreSQL**.
* **IA & Agents / RAG (Membre 2) :** Recherche sémantique sur rapports PDF (`pgvector`) et architecture multi-agents (**LangGraph** / LangChain).
* **Software Engineering & DevOps (Membre 3) :** API REST asynchrone (**FastAPI**), interface utilisateur interactive type chat (**Streamlit**) et conteneurisation globale (**Docker Compose**).

---

## 🛠️ Stack Technique
* **Langage :** Python 3.10+
* **Backend :** FastAPI, Uvicorn
* **Frontend :** Streamlit, Plotly, Pandas
* **Base de données :** PostgreSQL (`pgvector`)
* **DevOps :** Docker & Docker Compose

---

## 🚀 Guide de Lancement rapide (via Docker Compose)

Pour lancer toute l'application (Backend + Frontend) d'un seul coup :

1. Assure-toi d'avoir **Docker** et **Docker Compose** installés sur ta machine.
2. Clone le dépôt et place-toi à la racine du projet.
3. Lance la commande suivante :
   ```bash
   docker compose up --build