# data_engineering - Pipeline de donnees et analytics

Partie "Data Engineering & Analytics" (Tache 1) du Copilote d'Analyse Financiere & BI.
Branche : `feature/data-pipeline`.

## Contenu

| Fichier | Role |
|---------|------|
| `scripts_etl/clean_data.py` | Nettoyage Pandas du dataset (doublons, dates, types, categories) |
| `sql/schema.sql` | Tables `sales`, `clients`, `categories` + vue `v_sales_enriched` |
| `scripts_etl/ingest.py` | Chargement du CSV propre dans PostgreSQL (idempotent) |
| `analytics.py` | KPIs et graphiques Plotly reutilisables |
| `run_all.ps1` | Execute tout le pipeline sous Windows en une commande |
| `tests/` | Tests pytest (nettoyage et analytics) |

## Prerequis

- Python 3.10+
- Docker Desktop (PostgreSQL avec pgvector)

## Installation

```powershell
py -m venv venv
venv\Scripts\Activate.ps1
pip install -r data_engineering/requirements.txt
Copy-Item .env.example .env
```

## Lancer tout le pipeline (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File .\data_engineering\run_all.ps1 -Csv "data_engineering\data\raw\Sample - Superstore.csv"
```

Option `-DateFormat "%d/%m/%Y"` si les dates du CSV sont au format jour/mois/annee.

## Etapes manuelles

```powershell
# 1. PostgreSQL
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=copilot -p 5432:5432 -v pgdata:/var/lib/postgresql/data pgvector/pgvector:pg16
docker cp data_engineering\sql\schema.sql pg:/tmp/schema.sql
docker exec pg psql -U postgres -d copilot -f /tmp/schema.sql

# 2. Nettoyage puis ingestion
python -m data_engineering.scripts_etl.clean_data --input "data_engineering\data\raw\<fichier>.csv"
python -m data_engineering.scripts_etl.ingest

# 3. Tests
python -m pytest data_engineering/tests -v
```

Linux / macOS : remplacer `venv\Scripts\Activate.ps1` par `source venv/bin/activate`.

## Utilisation d'analytics

```python
from data_engineering.analytics import (
    load_sales, aggregate, monthly_revenue, forecast_next_month,
    get_kpi_summary, plot_line_chart, plot_bar_chart, plot_pie_chart,
)

df = load_sales()                                  # filtres : start_date, end_date, region, category
kpis = get_kpi_summary(df)                         # ou get_kpi_summary() sans argument
fig = plot_bar_chart(aggregate(df, "region"), "region", "sales_amount")
fig_json = fig.to_json()                           # pour l'API
```

Toutes les fonctions `plot_*` retournent une `plotly.graph_objects.Figure` et n'affichent rien.

## Schema de la vue `v_sales_enriched` (conseillee pour le Text-to-SQL)

| Colonne | Type | Description |
|---------|------|-------------|
| order_id | text | identifiant de commande |
| date | date | date de commande |
| product_id, product_name | text | produit |
| category, sub_category | text | categorie |
| client_id, client_name | text | client |
| segment | text | Consumer / Corporate / Home Office |
| region | text | region |
| sales_amount | numeric | chiffre d'affaires de la ligne |
| quantity | int | quantite |
| discount | numeric | remise (0 a 1) |
| profit | numeric | profit (peut etre negatif) |

## Notes

- `DATABASE_URL` est lu dans `.env` (voir `.env.example`). Le `.env` n'est jamais commite.
- Les donnees brutes (`data/raw/`) ne sont pas versionnees.
- Le rapport de nettoyage est genere dans `data/reports/cleaning_report.json`.
- L'extension pgvector n'est pas activee ici : elle est geree par le Membre 2.
