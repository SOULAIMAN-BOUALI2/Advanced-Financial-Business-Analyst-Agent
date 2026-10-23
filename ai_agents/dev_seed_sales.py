"""DEV ONLY: create FAKE sales data so the Text-to-SQL tool can be tested
before Member 1 delivers the real database.

    python -m ai_agents.dev_seed_sales

Never run this against the shared database.
"""
import os
import random
from datetime import date, timedelta

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

PRODUCTS = [
    (1, "Laptop Pro 15", "Technology", 1200),
    (2, "Wireless Mouse", "Technology", 25),
    (3, "Office Chair", "Furniture", 180),
    (4, "Standing Desk", "Furniture", 450),
    (5, "Printer Paper A4", "Office Supplies", 8),
    (6, "Notebook Pack", "Office Supplies", 12),
    (7, "Monitor 27in", "Technology", 300),
    (8, "Bookcase", "Furniture", 220),
]
REGIONS = ["Europe", "Africa", "Asia", "Americas"]


def main():
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql+psycopg://")
    engine = create_engine(url)
    random.seed(42)

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS sales"))
        conn.execute(text("DROP TABLE IF EXISTS products"))
        conn.execute(text(
            "CREATE TABLE products (product_id INT PRIMARY KEY, product_name TEXT, category TEXT)"
        ))
        conn.execute(text(
            """CREATE TABLE sales (
                id SERIAL PRIMARY KEY, date DATE, product_id INT REFERENCES products(product_id),
                region TEXT, sales_amount NUMERIC(12,2), quantity INT, profit NUMERIC(12,2))"""
        ))
        conn.execute(
            text("INSERT INTO products VALUES (:id, :name, :cat)"),
            [{"id": p[0], "name": p[1], "cat": p[2]} for p in PRODUCTS],
        )

        start = date(2024, 1, 1)
        rows = []
        for _ in range(600):
            pid, _, _, price = random.choice(PRODUCTS)
            qty = random.randint(1, 10)
            amount = round(price * qty * random.uniform(0.85, 1.0), 2)
            profit = round(amount * random.uniform(-0.05, 0.35), 2)
            rows.append({
                "d": start + timedelta(days=random.randint(0, 729)),
                "p": pid, "r": random.choice(REGIONS), "a": amount, "q": qty, "pr": profit,
            })
        conn.execute(
            text("INSERT INTO sales (date, product_id, region, sales_amount, quantity, profit) "
                 "VALUES (:d, :p, :r, :a, :q, :pr)"),
            rows,
        )
    print("Fake data created: 8 products, 600 sales (2024-2025).")


if __name__ == "__main__":
    main()
