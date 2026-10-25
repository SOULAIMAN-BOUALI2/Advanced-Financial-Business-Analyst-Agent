# GenInvest Copilot

GenInvest Copilot est un assistant d'analyse financière combinant :

- des données de ventes tabulaires stockées dans PostgreSQL ;
- un agent Text-to-SQL sécurisé ;
- des indicateurs et graphiques Plotly ;
- une recherche RAG optionnelle sur des rapports PDF avec pgvector ;
- une API FastAPI et une interface Streamlit ;
- une orchestration Docker Compose.

Le projet peut fonctionner uniquement avec les données tabulaires. Les PDF et le
RAG sont une fonctionnalité complémentaire.

## 1. Prérequis

- Linux, macOS ou Windows avec Docker Desktop ;
- Docker Compose v2 (`docker compose`) ;
- Python 3.12 pour l'exécution locale des scripts ;
- une clé Google Gemini pour les réponses de l'agent et, si nécessaire, les
  embeddings PDF.

Vérifier Docker :

```bash
docker --version
docker compose version
```

## 2. Configuration de l'environnement

Copier le modèle de configuration :

```bash
cp .env.example .env
```

Dans [`.env`](./.env), renseigner au minimum :

```env
POSTGRES_DB=geninvest
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5433
GOOGLE_API_KEY=VOTRE_CLE_GEMINI
```

`POSTGRES_PORT` est le port PostgreSQL exposé sur la machine hôte. Le port
interne Docker reste `5432`. Si le port `5432` est libre, utiliser
`POSTGRES_PORT=5432`.

Ne jamais publier `.env` : il contient une clé secrète et est ignoré par Git.

## 3. Données utilisées

### Données tabulaires

Le projet utilise un dataset de ventes de type **Sample Superstore**. Le fichier
brut doit être placé dans :

```text
data_engineering/data/raw/
```

Exemple :

```text
data_engineering/data/raw/Sample - Superstore.csv
```

Le script de nettoyage produit :

```text
data_engineering/data/clean/sales_clean.csv
data_engineering/data/reports/cleaning_report.json
```

Le pipeline traite les doublons, les dates, les types numériques, les valeurs
manquantes et les incohérences métier.

### Documents PDF (optionnels)

Les rapports PDF destinés au RAG doivent être placés dans :

```text
data/pdfs/
```

Ils sont découpés en chunks puis vectorisés dans PostgreSQL/pgvector. Le dossier
`data/pdfs/` est ignoré par Git pour éviter de versionner des documents volumineux.

## 4. Installation locale des dépendances

Cette étape est nécessaire pour lancer le nettoyage, l'ingestion ou les tests
depuis la machine hôte :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r data_engineering/requirements.txt
```

Les dépendances IA complètes sont déjà installées dans l'image Docker backend.
Pour les utiliser localement :

```bash
pip install -r ai_agents/requirements.txt
```

## 5. Démarrage de PostgreSQL et de l'application

Depuis la racine du projet :

```bash
sudo docker compose up -d --build
```

Les services sont alors disponibles à ces adresses :

| Service | Adresse |
|---|---|
| Frontend Streamlit | http://localhost:8501 |
| API FastAPI | http://localhost:8000 |
| PostgreSQL | localhost:${POSTGRES_PORT}, base `geninvest` |

Si le port externe du backend est occupé, modifier dans
[docker-compose.yml](./docker-compose.yml) :

```yaml
ports:
  - "8001:8000"
```

L'API sera alors accessible sur `http://localhost:8001`. Le frontend continue
à utiliser `http://backend:8000` dans le réseau Docker.

Vérifier l'état des conteneurs :

```bash
sudo docker compose ps
```

Afficher les logs :

```bash
sudo docker compose logs -f backend
sudo docker compose logs -f frontend
```

## 6. Nettoyer et charger les données tabulaires

Avec l'environnement virtuel activé, placer le CSV brut dans
`data_engineering/data/raw/`, puis exécuter :

```bash
python -m data_engineering.scripts_etl.clean_data \
  --input "data_engineering/data/raw/Sample - Superstore.csv"
```

Charger le CSV nettoyé dans PostgreSQL :

```bash
sudo docker compose run --rm \
  backend \
  python -m data_engineering.scripts_etl.ingest \
  --input /app/data_engineering/data/clean/sales_clean.csv
```

Vérifier l'importation :

```bash
sudo docker compose exec db psql -U postgres -d geninvest \
  -c "SELECT COUNT(*) FROM sales;"

sudo docker compose exec db psql -U postgres -d geninvest \
  -c "SELECT * FROM v_sales_enriched LIMIT 5;"
```

L'ingestion remplit les tables `categories`, `clients` et `sales`. Elle est
transactionnelle et remplace les lignes de `sales` pour éviter les données
partiellement chargées.

## 7. Indexer les PDF (optionnel)

Cette étape nécessite une clé Gemini valide et des PDF dans `data/pdfs/`.

```bash
sudo docker compose --profile index run --rm pdf-indexer
```

Le service utilise [index_pdfs.py](./ai_agents/index_pdfs.py). Il crée
automatiquement les tables `langchain_pg_collection` et
`langchain_pg_embedding`, puis enregistre les embeddings dans PostgreSQL.

Vérifier le nombre d'embeddings :

```bash
sudo docker compose exec db psql -U postgres -d geninvest \
  -c "SELECT COUNT(*) FROM langchain_pg_embedding;"
```

Si l'API Gemini renvoie `503`, `429` ou `GoogleGenerativeAIError`, attendre,
vérifier la clé et le quota, puis relancer l'indexeur. L'indexation PDF n'est
pas nécessaire pour les questions SQL et les graphiques tabulaires.

## 8. Tester l'application

Tester l'API :

```bash
curl http://localhost:8000/
curl http://localhost:8000/api/dashboard
```

Tester le chat :

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Quel est le chiffre d’affaires total par région ?"}'
```

Questions utiles dans l'interface :

- `Quel est le chiffre d’affaires total par région ?`
- `Quelle région réalise le meilleur chiffre d’affaires ?`
- `Montre-moi un graphique en barres du chiffre d’affaires par région.`
- `Trace l’évolution mensuelle des ventes.`

Tester les tests unitaires :

```bash
python -m pytest data_engineering/tests tests -v
```

## 9. Architecture du projet

```text
.
├── ai_agents/
│   ├── main_agent.py       # point d'entrée run_copilot_agent
│   ├── workflow.py         # routeur LangGraph, SQL, RAG et graphiques
│   ├── sql_tool.py         # Text-to-SQL en lecture seule
│   ├── rag_engine.py       # recherche pgvector
│   ├── index_pdfs.py       # indexation des rapports PDF
│   └── evaluation/         # dataset et rapport LLMOps
├── backend/
│   ├── main.py             # API FastAPI
│   └── dockerfile
├── frontend/
│   ├── app.py              # interface Streamlit
│   └── dockerfile
├── data_engineering/
│   ├── analytics.py        # KPI et fonctions Plotly
│   ├── scripts_etl/
│   │   ├── clean_data.py   # nettoyage du CSV brut
│   │   └── ingest.py       # chargement PostgreSQL
│   ├── sql/schema.sql      # schéma et vue SQL
│   └── tests/
├── data/
│   └── pdfs/               # rapports PDF optionnels
├── docker-compose.yml
└── requirements.txt
```

## 10. Flux de fonctionnement

### Question tabulaire

```text
Utilisateur
    ↓
Streamlit
    ↓
FastAPI /api/chat
    ↓
Agent LangGraph
    ↓
LLM → génération SQL
    ↓
validation SELECT + transaction read-only
    ↓
PostgreSQL / v_sales_enriched
    ↓
réponse ou graphique Plotly
```

Le LLM choisit le type de graphique et les colonnes sous forme de JSON. Le code
de visualisation reste dans [analytics.py](./data_engineering/analytics.py) :
le modèle ne génère ni n'exécute du code Python.

### Question documentaire

```text
Question
    ↓
embeddings de la question
    ↓
pgvector / langchain_pg_embedding
    ↓
chunks PDF et sources
    ↓
synthèse de l'agent
```

## 11. Arrêt et réinitialisation

Arrêter les services sans supprimer les données :

```bash
sudo docker compose down
```

Supprimer aussi le volume PostgreSQL (opération destructive, toutes les données
de la base seront perdues) :

```bash
sudo docker compose down -v
```

Après une suppression du volume, relancer `docker compose up -d` recrée
l'extension `vector`, les tables métier et la vue depuis
[schema.sql](./data_engineering/sql/schema.sql).
