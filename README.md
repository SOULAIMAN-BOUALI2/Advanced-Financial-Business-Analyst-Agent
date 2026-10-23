# ⚙️ GenInvest Copilot - Backend, Frontend & DevOps (Membre 3)

Ce dossier contient la partie **Software Engineering & DevOps** de la plateforme GenInvest Copilot. Elle centralise l'API REST, l'interface utilisateur interactive et l'orchestration des conteneurs.

---

## 📂 Structure du Module
* `backend/` : API asynchrone développée avec **FastAPI**.
* `frontend/` : Interface utilisateur moderne de type chat et dashboard développée avec **Streamlit** et **Plotly**.
* `docker-compose.yml` : Fichier d'orchestration pour packager et lancer l'ensemble des services.

---

## 🛠️ Fonctionnalités implémentées
1. **API REST (FastAPI) :**
   * Route racine de test (`/`).
   * Route de récupération des KPIs (`/api/dashboard`).
   * Route de communication avec le copilote IA (`/api/chat`).
2. **Interface Utilisateur Pro (Streamlit) :**
   * Design épuré en mode conversationnel unifié (type ChatGPT).
   * Affichage dynamique de texte, de sources et de graphiques interactifs (Plotly).
3. **DevOps & Conteneurisation :**
   * Dockerfiles optimisés pour le backend et le frontend (Python 3.10-slim).
   * Orchestration complète via `Docker Compose`.

---

## 🚀 Guide de Lancement (Local ou Docker)

### Option 1 : Via Docker Compose (Recommandé)
Lance toute l'application d'un seul coup à la racine du projet :
```bash
sudo docker compose up --build