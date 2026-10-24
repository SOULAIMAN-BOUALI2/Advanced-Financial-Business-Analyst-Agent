"""Ingestion du CSV nettoye dans PostgreSQL (idempotent).

Usage (depuis la racine du depot) :
    python -m data_engineering.scripts_etl.ingest
    python -m data_engineering.scripts_etl.ingest --input data_engineering/data/clean/sales_clean.csv
"""
from __future__ import annotations

import argparse
import logging
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("ingest")


def get_engine():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL manquante : copier .env.example vers .env")
    return create_engine(url, pool_pre_ping=True)


def load_categories(conn, df: pd.DataFrame) -> pd.DataFrame:
    cats = df[["category", "sub_category"]].drop_duplicates()
    conn.execute(
        text(
            "INSERT INTO categories (category, sub_category) "
            "VALUES (:category, :sub_category) "
            "ON CONFLICT (category, sub_category) DO NOTHING"
        ),
        cats.to_dict("records"),
    )
    log.info("Categories : %d combinaisons", len(cats))
    return pd.read_sql(text("SELECT category_id, category, sub_category FROM categories"), conn)


def load_clients(conn, df: pd.DataFrame) -> None:
    clients = (
        df[["customer_id", "customer_name", "segment"]]
        .drop_duplicates(subset=["customer_id"])
        .rename(columns={"customer_id": "client_id", "customer_name": "client_name"})
    )
    conn.execute(
        text(
            "INSERT INTO clients (client_id, client_name, segment) "
            "VALUES (:client_id, :client_name, :segment) "
            "ON CONFLICT (client_id) DO NOTHING"
        ),
        clients.to_dict("records"),
    )
    log.info("Clients : %d", len(clients))


def load_sales(conn, df: pd.DataFrame, cat_map: pd.DataFrame) -> int:
    merged = df.merge(cat_map, on=["category", "sub_category"], how="left")
    if merged["category_id"].isna().any():
        raise ValueError("Des lignes n'ont pas de category_id : verifier le mapping")

    sales = pd.DataFrame({
        "order_id": merged["order_id"],
        "date": merged["order_date"].dt.date,
        "product_id": merged["product_id"],
        "product_name": merged["product_name"],
        "category_id": merged["category_id"].astype(int),
        "client_id": merged["customer_id"],
        "region": merged["region"],
        "sales_amount": merged["sales"],
        "quantity": merged["quantity"],
        "discount": merged["discount"],
        "profit": merged["profit"],
    })

    conn.execute(text("TRUNCATE TABLE sales RESTART IDENTITY"))
    sales.to_sql("sales", conn, if_exists="append", index=False,
                 chunksize=1000, method="multi")
    return len(sales)


def run(path: str) -> None:
    df = pd.read_csv(path, parse_dates=["order_date"])
    log.info("CSV lu : %d lignes", len(df))
    engine = get_engine()

    with engine.begin() as conn:  # transaction unique : tout ou rien
        cat_map = load_categories(conn, df)
        load_clients(conn, df)
        n = load_sales(conn, df, cat_map)
        total_db = conn.execute(text("SELECT SUM(sales_amount) FROM sales")).scalar()
        count_db = conn.execute(text("SELECT COUNT(*) FROM sales")).scalar()

    assert count_db == n == len(df), f"Ecart de lignes : {count_db} vs {len(df)}"
    assert abs(float(total_db) - df["sales"].sum()) < 1.0, "Ecart sur le CA total"
    log.info("Ingestion OK : %d lignes, CA total = %.2f", count_db, float(total_db))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default="data_engineering/data/clean/sales_clean.csv")
    run(ap.parse_args().input)
