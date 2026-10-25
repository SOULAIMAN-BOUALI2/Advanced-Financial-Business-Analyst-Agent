-- Schema PostgreSQL du Copilote BI (Tache 1 - data-pipeline)
-- Commentaires volontairement sans accents (compatibilite Windows).
-- ATTENTION : ce script supprime et recree les tables (usage developpement).

-- L'image pgvector l'expose, mais l'extension doit etre activee dans chaque base.
CREATE EXTENSION IF NOT EXISTS vector;

-- Les tables langchain_pg_collection et langchain_pg_embedding sont creees
-- automatiquement par PGVector lors de la premiere execution de index_pdfs.py.

DROP VIEW IF EXISTS v_sales_enriched;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS clients;
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    category_id   SERIAL PRIMARY KEY,
    category      VARCHAR(100) NOT NULL,
    sub_category  VARCHAR(100) NOT NULL,
    CONSTRAINT uq_category UNIQUE (category, sub_category)
);

CREATE TABLE clients (
    client_id     VARCHAR(50) PRIMARY KEY,
    client_name   VARCHAR(150) NOT NULL,
    segment       VARCHAR(50)
);

CREATE TABLE sales (
    id            SERIAL PRIMARY KEY,
    order_id      VARCHAR(50)   NOT NULL,
    date          DATE          NOT NULL,
    product_id    VARCHAR(50)   NOT NULL,
    product_name  VARCHAR(255),
    category_id   INT REFERENCES categories(category_id),
    client_id     VARCHAR(50) REFERENCES clients(client_id),
    region        VARCHAR(50),
    sales_amount  NUMERIC(12,2) NOT NULL CHECK (sales_amount >= 0),
    quantity      INT           NOT NULL CHECK (quantity > 0),
    discount      NUMERIC(4,2)  DEFAULT 0,
    profit        NUMERIC(12,2)
);

CREATE INDEX idx_sales_date     ON sales(date);
CREATE INDEX idx_sales_region   ON sales(region);
CREATE INDEX idx_sales_client   ON sales(client_id);
CREATE INDEX idx_sales_category ON sales(category_id);
CREATE INDEX idx_sales_order    ON sales(order_id);

-- Vue "a plat" recommandee pour l'agent Text-to-SQL (aucune jointure a ecrire)
CREATE OR REPLACE VIEW v_sales_enriched AS
SELECT s.id, s.order_id, s.date, s.product_id, s.product_name,
       c.category, c.sub_category,
       s.client_id, cl.client_name, cl.segment,
       s.region, s.sales_amount, s.quantity, s.discount, s.profit
FROM sales s
LEFT JOIN categories c  ON c.category_id = s.category_id
LEFT JOIN clients   cl  ON cl.client_id  = s.client_id;
