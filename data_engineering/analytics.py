"""Module d'analyse et de visualisation du Copilote BI.

Contrat stable (utilise par le Membre 2 et le Membre 3) :
    get_kpi_summary(df=None, **filtres) -> dict
    plot_line_chart(df, x, y, ...)      -> go.Figure
    plot_bar_chart(df, x, y, ...)       -> go.Figure
    plot_pie_chart(df, labels, values)  -> go.Figure
Utilitaires :
    load_sales(...)                     -> pd.DataFrame
    aggregate(df, by, metric, ...)      -> pd.DataFrame
    monthly_revenue(df)                 -> pd.DataFrame
    forecast_next_month(monthly_df)     -> float

Les fonctions graphiques retournent TOUJOURS une figure Plotly et ne
l'affichent jamais (pas de fig.show()).
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --------------------------------------------------------------------------- #
# Chargement des donnees
# --------------------------------------------------------------------------- #
_VIEW_QUERY = """
SELECT order_id, date, product_id, product_name, category, sub_category,
       client_id, client_name, segment, region,
       sales_amount, quantity, discount, profit
FROM v_sales_enriched
WHERE 1=1
"""


def load_sales(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    region: Optional[str] = None,
    category: Optional[str] = None,
    engine=None,
) -> pd.DataFrame:
    """Charge les ventes depuis PostgreSQL (vue v_sales_enriched) avec filtres.

    Args:
        start_date: borne basse incluse, 'YYYY-MM-DD'.
        end_date:   borne haute incluse, 'YYYY-MM-DD'.
        region:     ex. 'West'.
        category:   ex. 'Technology'.
        engine:     moteur SQLAlchemy (cree depuis DATABASE_URL si None).
    """
    from sqlalchemy import create_engine, text

    if engine is None:
        from dotenv import load_dotenv

        load_dotenv()
        engine = create_engine(os.environ["DATABASE_URL"])

    query, params = _VIEW_QUERY, {}
    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date
    if region:
        query += " AND region = :region"
        params["region"] = region
    if category:
        query += " AND category = :category"
        params["category"] = category

    df = pd.read_sql(text(query), engine, params=params)
    df["date"] = pd.to_datetime(df["date"])
    for col in ("sales_amount", "profit", "discount"):
        df[col] = df[col].astype(float)
    return df


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def _require_columns(df: pd.DataFrame, *cols: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Colonnes introuvables : {missing}. Colonnes disponibles : {list(df.columns)}"
        )


def _empty_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        annotations=[dict(text="Aucune donnee a afficher", showarrow=False,
                          xref="paper", yref="paper", x=0.5, y=0.5)],
    )
    return fig


def aggregate(df: pd.DataFrame, by: str, metric: str = "sales_amount",
              agg: str = "sum", top_n: Optional[int] = None) -> pd.DataFrame:
    """Agrege `metric` par `by` et trie par ordre decroissant."""
    _require_columns(df, by, metric)
    out = (df.groupby(by, as_index=False)[metric].agg(agg)
             .sort_values(metric, ascending=False))
    return out.head(top_n) if top_n else out


def monthly_revenue(df: pd.DataFrame, date_col: str = "date",
                    metric: str = "sales_amount") -> pd.DataFrame:
    """Serie mensuelle : colonnes `month` (debut de mois) et `metric`."""
    _require_columns(df, date_col, metric)
    return (df.set_index(date_col)[metric].resample("MS").sum()
              .reset_index().rename(columns={date_col: "month"}))


def forecast_next_month(monthly_df: pd.DataFrame, value_col: str = "sales_amount") -> float:
    """Prevision naive du mois suivant : regression lineaire sur les 6 derniers mois."""
    import numpy as np

    _require_columns(monthly_df, value_col)
    y = monthly_df[value_col].tail(6).to_numpy(dtype=float)
    if len(y) < 2:
        return float(y[-1]) if len(y) else 0.0
    slope, intercept = np.polyfit(np.arange(len(y)), y, 1)
    return float(slope * len(y) + intercept)


# --------------------------------------------------------------------------- #
# KPIs
# --------------------------------------------------------------------------- #
def get_kpi_summary(
    df: Optional[pd.DataFrame] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    region: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """Calcule les indicateurs cles.

    Si `df` est None, les donnees sont chargees depuis PostgreSQL avec les
    filtres fournis. Sinon, les calculs portent sur le DataFrame recu.

    Returns:
        dict : total_sales, total_profit, profit_margin_pct, total_orders,
        total_quantity, avg_basket, nb_clients, best_region, best_category,
        period_start, period_end.
    """
    if df is None:
        df = load_sales(start_date, end_date, region, category)
    if df.empty:
        return {"total_sales": 0.0, "total_profit": 0.0, "profit_margin_pct": 0.0,
                "total_orders": 0, "total_quantity": 0, "avg_basket": 0.0,
                "nb_clients": 0, "best_region": None, "best_category": None,
                "period_start": None, "period_end": None}

    _require_columns(df, "sales_amount", "profit", "order_id", "quantity")
    total_sales = float(df["sales_amount"].sum())
    total_profit = float(df["profit"].sum())
    total_orders = int(df["order_id"].nunique())

    return {
        "total_sales": round(total_sales, 2),
        "total_profit": round(total_profit, 2),
        "profit_margin_pct": round(100 * total_profit / total_sales, 2) if total_sales else 0.0,
        "total_orders": total_orders,
        "total_quantity": int(df["quantity"].sum()),
        "avg_basket": round(total_sales / total_orders, 2) if total_orders else 0.0,
        "nb_clients": int(df["client_id"].nunique()) if "client_id" in df else None,
        "best_region": df.groupby("region")["sales_amount"].sum().idxmax()
        if "region" in df else None,
        "best_category": df.groupby("category")["sales_amount"].sum().idxmax()
        if "category" in df else None,
        "period_start": str(df["date"].min().date()) if "date" in df else None,
        "period_end": str(df["date"].max().date()) if "date" in df else None,
    }


# --------------------------------------------------------------------------- #
# Graphiques (retournent TOUJOURS une go.Figure)
# --------------------------------------------------------------------------- #
def plot_line_chart(df: pd.DataFrame, x: str, y: str,
                    title: Optional[str] = None, color: Optional[str] = None) -> go.Figure:
    """Graphique de tendance temporelle.

    Args:
        df: DataFrame source (ex. sortie de `monthly_revenue`).
        x: colonne en abscisse (date / mois).
        y: colonne numerique en ordonnee.
        title: titre optionnel.
        color: colonne optionnelle pour tracer plusieurs courbes.
    """
    _require_columns(df, x, y)
    title = title or f"Evolution de {y} par {x}"
    if df.empty:
        return _empty_figure(title)
    fig = px.line(df.sort_values(x), x=x, y=y, color=color, markers=True, title=title)
    fig.update_layout(template="plotly_white", hovermode="x unified")
    return fig


def plot_bar_chart(df: pd.DataFrame, x: str, y: str,
                   title: Optional[str] = None, color: Optional[str] = None,
                   horizontal: bool = False) -> go.Figure:
    """Histogramme de comparaison par categorie ou region."""
    _require_columns(df, x, y)
    title = title or f"{y} par {x}"
    if df.empty:
        return _empty_figure(title)
    if horizontal:
        fig = px.bar(df, x=y, y=x, color=color, orientation="h", title=title)
    else:
        fig = px.bar(df, x=x, y=y, color=color, title=title)
    fig.update_layout(template="plotly_white")
    return fig


def plot_pie_chart(df: pd.DataFrame, labels: str, values: str,
                   title: Optional[str] = None, donut: bool = False) -> go.Figure:
    """Diagramme circulaire de repartition."""
    _require_columns(df, labels, values)
    title = title or f"Repartition de {values} par {labels}"
    if df.empty:
        return _empty_figure(title)
    fig = px.pie(df, names=labels, values=values, title=title, hole=0.4 if donut else 0)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


# --------------------------------------------------------------------------- #
# Verification manuelle : python -m data_engineering.analytics
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    data = load_sales()
    print(get_kpi_summary(data))
    monthly = monthly_revenue(data)
    print("Prevision du mois prochain :", round(forecast_next_month(monthly), 2))
    plot_line_chart(monthly, "month", "sales_amount").write_html("trend.html")
    plot_bar_chart(aggregate(data, "region"), "region", "sales_amount").write_html("bar.html")
    plot_pie_chart(aggregate(data, "category"), "category", "sales_amount").write_html("pie.html")
    print("Graphiques generes : trend.html, bar.html, pie.html")
