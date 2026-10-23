"""Nettoyage du dataset de ventes (Superstore / Global Superstore).

Usage (depuis la racine du depot) :
    python -m data_engineering.scripts_etl.clean_data \
        --input "data_engineering/data/raw/Sample - Superstore.csv"

Le format de date est detecte automatiquement (le format passe en
parametre est essaye en premier).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("clean_data")

# Colonnes finales attendues par la base de donnees
FINAL_COLUMNS = [
    "order_id", "order_date", "product_id", "product_name",
    "category", "sub_category", "customer_id", "customer_name",
    "segment", "region", "sales", "quantity", "discount", "profit",
]

# Colonnes indispensables : sans elles on ne peut pas continuer
REQUIRED = ["order_id", "order_date", "product_id", "sales", "quantity"]

# Colonnes facultatives et leur valeur par defaut si elles sont absentes
OPTIONAL_DEFAULTS = {
    "category": "Unknown",
    "sub_category": "Unknown",
    "customer_id": "UNKNOWN",
    "customer_name": "Unknown",
    "segment": "Unknown",
    "region": "Unknown",
    "discount": 0.0,
    "profit": 0.0,
}

DATE_FORMATS = [
    "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%m-%d-%Y",
    "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S",
]


def to_snake_case(columns) -> list[str]:
    """'Sub-Category' -> 'sub_category'."""
    return [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in columns]


def read_raw(path: str) -> pd.DataFrame:
    """Lit le CSV en essayant utf-8 puis latin-1."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            log.info("Encodage %s non applicable, essai suivant", enc)
    raise ValueError("Impossible de lire le fichier")


def parse_dates(series: pd.Series, preferred: str | None) -> tuple[pd.Series, str]:
    """Essaie plusieurs formats et garde celui qui convertit le plus de lignes."""
    s = series.astype(str).str.strip()
    candidates = ([preferred] if preferred else []) + [f for f in DATE_FORMATS if f != preferred]
    best, best_fmt, best_ok = None, None, -1
    for fmt in candidates:
        parsed = pd.to_datetime(s, format=fmt, errors="coerce")
        ok = int(parsed.notna().sum())
        if ok > best_ok:
            best, best_fmt, best_ok = parsed, fmt, ok
        if ok == len(s):
            break
    return best, best_fmt


def clean(
    path_in: str,
    path_out: str = "data_engineering/data/clean/sales_clean.csv",
    date_format: str | None = "%m/%d/%Y",
    report_path: str = "data_engineering/data/reports/cleaning_report.json",
) -> pd.DataFrame:
    report: dict = {}
    df = read_raw(path_in)
    report["rows_raw"] = len(df)
    log.info("Lignes brutes : %d", len(df))

    # 1. Noms de colonnes
    df.columns = to_snake_case(df.columns)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(
            f"Colonnes indispensables introuvables : {missing}. "
            f"Colonnes presentes : {list(df.columns)}"
        )

    # 2. Doublons
    n_before = len(df)
    df = df.drop_duplicates()
    if "row_id" in df.columns:
        df = df.drop_duplicates(subset=["row_id"])
    report["duplicates_removed"] = n_before - len(df)

    # 3. Dates (format detecte automatiquement)
    df["order_date"], used_fmt = parse_dates(df["order_date"], date_format)
    report["date_format_used"] = used_fmt
    report["invalid_dates"] = int(df["order_date"].isna().sum())
    log.info("Format de date retenu : %s (%d dates invalides)", used_fmt, report["invalid_dates"])

    # 4. Types numeriques
    for col in ("sales", "profit", "discount", "quantity"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 5. Valeurs manquantes
    report["missing_before"] = {k: int(v) for k, v in df.isna().sum().items() if v}
    n_before = len(df)
    df = df.dropna(subset=REQUIRED)
    report["rows_dropped_missing_critical"] = n_before - len(df)

    # 6. Colonnes facultatives : valeurs par defaut si absentes ou vides
    if "product_name" not in df.columns:
        df["product_name"] = df["product_id"]
    for col, default in OPTIONAL_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
        else:
            df[col] = df[col].fillna(default)
    df["product_name"] = df["product_name"].fillna(df["product_id"])
    df["quantity"] = df["quantity"].astype(int)

    # 7. Standardisation des textes
    for col in ("region", "category", "sub_category", "segment"):
        df[col] = df[col].astype(str).str.strip().str.title()
    for col in ("customer_name", "product_name"):
        df[col] = df[col].astype(str).str.strip()
    for col in ("order_id", "product_id", "customer_id"):
        df[col] = df[col].astype(str).str.strip().str.upper()

    # 8. Regles de coherence metier
    mask_invalid = (df["quantity"] <= 0) | (df["sales"] < 0)
    report["rows_dropped_invalid_values"] = int(mask_invalid.sum())
    df = df[~mask_invalid]

    # 9. Valeurs aberrantes : signalees, jamais supprimees
    q1, q3 = df["sales"].quantile([0.25, 0.75])
    report["sales_outliers_flagged"] = int((df["sales"] > q3 + 3 * (q3 - q1)).sum())

    # 10. Export
    df["sales"] = df["sales"].round(2)
    df["profit"] = df["profit"].round(2)
    df = df[FINAL_COLUMNS].sort_values("order_date").reset_index(drop=True)

    report["rows_clean"] = len(df)
    report["date_min"] = str(df["order_date"].min().date())
    report["date_max"] = str(df["order_date"].max().date())

    Path(path_out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path_out, index=False)

    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Rapport : %s", json.dumps(report, ensure_ascii=False))
    log.info("CSV propre : %s (%d lignes)", path_out, len(df))
    return df


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", default="data_engineering/data/clean/sales_clean.csv")
    p.add_argument("--date-format", default="%m/%d/%Y")
    a = p.parse_args()
    clean(a.input, a.output, a.date_format)
